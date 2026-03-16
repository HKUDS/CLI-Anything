"""Draw.io XML manipulation utilities.

Draw.io files (.drawio) are XML-based, using the mxGraph format.
We manipulate them directly by parsing and modifying the XML tree.

Structure:
    <mxfile>
      <diagram id="..." name="Page-1">
        <mxGraphModel dx="..." dy="..." ...>
          <root>
            <mxCell id="0"/>                     ← root container
            <mxCell id="1" parent="0"/>          ← default layer
            <mxCell id="2" value="Hello"         ← shapes/edges
                    style="rounded=1;..."
                    vertex="1" parent="1">
              <mxGeometry x="10" y="20"
                          width="120" height="60"
                          as="geometry"/>
            </mxCell>
          </root>
        </mxGraphModel>
      </diagram>
    </mxfile>
"""

import os
import uuid
from xml.etree import ElementTree as ET
from typing import Optional


# ============================================================================
# File I/O
# ============================================================================

def parse_drawio(path: str) -> ET.Element:
    """Parse a .drawio XML file. Returns the root <mxfile> element."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    tree = ET.parse(path)
    return tree.getroot()


def write_drawio(root: ET.Element, path: str) -> None:
    """Write an XML tree to a .drawio file."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, xml_declaration=True, encoding="utf-8")


def xml_to_string(root: ET.Element) -> str:
    """Serialize an XML tree to a UTF-8 string."""
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode")


# ============================================================================
# Create blank diagram
# ============================================================================

def create_blank_diagram(page_width: int = 850, page_height: int = 1100,
                         grid_size: int = 10) -> ET.Element:
    """Create a new blank draw.io diagram XML.

    Args:
        page_width: Page width in pixels.
        page_height: Page height in pixels.
        grid_size: Grid snap size.

    Returns:
        Root <mxfile> element.
    """
    mxfile = ET.Element("mxfile")
    mxfile.set("host", "cli-anything")
    mxfile.set("agent", "cli-anything-drawio/1.0.0")
    mxfile.set("version", "24.0.0")

    diagram = ET.SubElement(mxfile, "diagram")
    diagram.set("id", _new_id("diagram"))
    diagram.set("name", "Page-1")

    model = ET.SubElement(diagram, "mxGraphModel")
    model.set("dx", "1200")
    model.set("dy", "800")
    model.set("grid", "1")
    model.set("gridSize", str(grid_size))
    model.set("guides", "1")
    model.set("tooltips", "1")
    model.set("connect", "1")
    model.set("arrows", "1")
    model.set("fold", "1")
    model.set("page", "1")
    model.set("pageScale", "1")
    model.set("pageWidth", str(page_width))
    model.set("pageHeight", str(page_height))
    model.set("math", "0")
    model.set("shadow", "0")

    root = ET.SubElement(model, "root")

    # Default system cells (always present)
    cell0 = ET.SubElement(root, "mxCell")
    cell0.set("id", "0")

    cell1 = ET.SubElement(root, "mxCell")
    cell1.set("id", "1")
    cell1.set("parent", "0")

    return mxfile


# ============================================================================
# Navigation helpers
# ============================================================================

def get_diagram(mxfile: ET.Element, index: int = 0) -> ET.Element:
    """Get a <diagram> element by index."""
    diagrams = mxfile.findall("diagram")
    if not diagrams:
        raise RuntimeError("No diagram found in file")
    if index >= len(diagrams):
        raise IndexError(f"Diagram index {index} out of range (have {len(diagrams)})")
    return diagrams[index]


def get_model(mxfile: ET.Element, diagram_index: int = 0) -> ET.Element:
    """Get the <mxGraphModel> element."""
    diagram = get_diagram(mxfile, diagram_index)
    model = diagram.find("mxGraphModel")
    if model is None:
        raise RuntimeError("No mxGraphModel found in diagram")
    return model


def get_root(mxfile: ET.Element, diagram_index: int = 0) -> ET.Element:
    """Get the <root> element containing all cells."""
    model = get_model(mxfile, diagram_index)
    root = model.find("root")
    if root is None:
        raise RuntimeError("No root element found in mxGraphModel")
    return root


# ============================================================================
# Query operations
# ============================================================================

def get_all_cells(mxfile: ET.Element, diagram_index: int = 0) -> list[ET.Element]:
    """Get all user mxCell elements (excluding system cells id=0 and id=1)."""
    root = get_root(mxfile, diagram_index)
    cells = []
    for cell in root.findall("mxCell"):
        cid = cell.get("id", "")
        if cid not in ("0", "1"):
            cells.append(cell)
    return cells


def get_vertices(mxfile: ET.Element, diagram_index: int = 0) -> list[ET.Element]:
    """Get all shape (vertex) cells."""
    return [c for c in get_all_cells(mxfile, diagram_index) if c.get("vertex") == "1"]


def get_edges(mxfile: ET.Element, diagram_index: int = 0) -> list[ET.Element]:
    """Get all edge (connector) cells."""
    return [c for c in get_all_cells(mxfile, diagram_index) if c.get("edge") == "1"]


def find_cell_by_id(mxfile: ET.Element, cell_id: str,
                    diagram_index: int = 0) -> Optional[ET.Element]:
    """Find a cell by its ID."""
    root = get_root(mxfile, diagram_index)
    for cell in root.iter("mxCell"):
        if cell.get("id") == cell_id:
            return cell
    return None


def get_cell_geometry(cell: ET.Element) -> dict:
    """Get the geometry of a cell as a dict."""
    geo = cell.find("mxGeometry")
    if geo is None:
        return {}
    return {
        "x": float(geo.get("x", "0")),
        "y": float(geo.get("y", "0")),
        "width": float(geo.get("width", "0")),
        "height": float(geo.get("height", "0")),
    }


def get_cell_info(cell: ET.Element) -> dict:
    """Get summary info for a cell."""
    info = {
        "id": cell.get("id", ""),
        "value": cell.get("value", ""),
        "style": cell.get("style", ""),
    }
    if cell.get("vertex") == "1":
        info["type"] = "vertex"
        info.update(get_cell_geometry(cell))
    elif cell.get("edge") == "1":
        info["type"] = "edge"
        info["source"] = cell.get("source", "")
        info["target"] = cell.get("target", "")
    return info


# ============================================================================
# Style parsing and manipulation
# ============================================================================

def parse_style(style_str: str) -> dict:
    """Parse a draw.io style string into a dict.

    Style format: "key1=value1;key2=value2;baseStyle;"
    Keys without values are treated as base style names (value="").
    """
    result = {}
    if not style_str:
        return result
    for part in style_str.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            result[k] = v
        else:
            result[part] = ""
    return result


def build_style(style_dict: dict) -> str:
    """Build a draw.io style string from a dict."""
    parts = []
    for k, v in style_dict.items():
        if v == "":
            parts.append(k)
        else:
            parts.append(f"{k}={v}")
    return ";".join(parts) + ";"


def set_style_property(cell: ET.Element, key: str, value: str) -> None:
    """Set a single style property on a cell."""
    style = parse_style(cell.get("style", ""))
    style[key] = value
    cell.set("style", build_style(style))


def remove_style_property(cell: ET.Element, key: str) -> None:
    """Remove a style property from a cell."""
    style = parse_style(cell.get("style", ""))
    style.pop(key, None)
    cell.set("style", build_style(style))


# ============================================================================
# Shape type presets
# ============================================================================

SHAPE_STYLES = {
    "rectangle": "rounded=0;whiteSpace=wrap;html=1;",
    "rounded": "rounded=1;whiteSpace=wrap;html=1;",
    "ellipse": "ellipse;whiteSpace=wrap;html=1;",
    "diamond": "rhombus;whiteSpace=wrap;html=1;",
    "triangle": "triangle;whiteSpace=wrap;html=1;",
    "hexagon": "shape=hexagon;perimeter=hexagonPerimeter2;whiteSpace=wrap;html=1;",
    "cylinder": "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;",
    "cloud": "ellipse;shape=cloud;whiteSpace=wrap;html=1;",
    "parallelogram": "shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;",
    "process": "shape=process;whiteSpace=wrap;html=1;backgroundOutline=1;",
    "document": "shape=document;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=0.27;",
    "callout": "shape=callout;whiteSpace=wrap;html=1;perimeter=calloutPerimeter;size=30;position=0.5;",
    "note": "shape=note;whiteSpace=wrap;html=1;backgroundOutline=1;size=15;",
    "actor": "shape=mxgraph.basic.person;whiteSpace=wrap;html=1;",
    "text": "text;html=1;align=center;verticalAlign=middle;resizable=0;points=[];autosize=1;",
}

EDGE_STYLES = {
    "straight": "edgeStyle=none;",
    "orthogonal": "edgeStyle=orthogonalEdgeStyle;rounded=0;",
    "curved": "edgeStyle=orthogonalEdgeStyle;curved=1;rounded=1;",
    "entity-relation": "edgeStyle=entityRelationEdgeStyle;",
}


# ============================================================================
# Mutation operations
# ============================================================================

def _new_id(prefix: str = "cell") -> str:
    """Generate a unique ID."""
    return f"{prefix}_{uuid.uuid4().hex}"


def add_vertex(mxfile: ET.Element, shape_type: str,
               x: float, y: float, width: float, height: float,
               label: str = "", parent: str = "1",
               diagram_index: int = 0) -> str:
    """Add a shape (vertex) to the diagram.

    Args:
        mxfile: Root mxfile element.
        shape_type: Shape preset name (see SHAPE_STYLES) or raw style string.
        x, y: Position.
        width, height: Dimensions.
        label: Text label for the shape.
        parent: Parent cell ID (default "1" = default layer).

    Returns:
        The new cell's ID.
    """
    root = get_root(mxfile, diagram_index)
    cell_id = _new_id("v")

    cell = ET.SubElement(root, "mxCell")
    cell.set("id", cell_id)
    cell.set("value", label)

    # Resolve style
    if shape_type in SHAPE_STYLES:
        style = SHAPE_STYLES[shape_type]
    else:
        style = shape_type if ";" in shape_type else f"{shape_type};"
    cell.set("style", style)
    cell.set("vertex", "1")
    cell.set("parent", parent)

    geo = ET.SubElement(cell, "mxGeometry")
    geo.set("x", str(x))
    geo.set("y", str(y))
    geo.set("width", str(width))
    geo.set("height", str(height))
    geo.set("as", "geometry")

    return cell_id


def add_edge(mxfile: ET.Element, source_id: str, target_id: str,
             edge_style: str = "orthogonal", label: str = "",
             parent: str = "1", diagram_index: int = 0) -> str:
    """Add an edge (connector) between two cells.

    Args:
        mxfile: Root mxfile element.
        source_id: Source cell ID.
        target_id: Target cell ID.
        edge_style: Edge style preset name (see EDGE_STYLES) or raw style string.
        label: Optional edge label.
        parent: Parent cell ID.

    Returns:
        The new edge's ID.
    """
    root = get_root(mxfile, diagram_index)
    edge_id = _new_id("e")

    cell = ET.SubElement(root, "mxCell")
    cell.set("id", edge_id)
    cell.set("value", label)

    # Resolve style
    if edge_style in EDGE_STYLES:
        style = EDGE_STYLES[edge_style]
    else:
        style = edge_style if ";" in edge_style else f"{edge_style};"
    cell.set("style", style)
    cell.set("edge", "1")
    cell.set("parent", parent)
    cell.set("source", source_id)
    cell.set("target", target_id)

    geo = ET.SubElement(cell, "mxGeometry")
    geo.set("relative", "1")
    geo.set("as", "geometry")

    return edge_id


def remove_cell(mxfile: ET.Element, cell_id: str,
                diagram_index: int = 0) -> bool:
    """Remove a cell by ID. Also removes edges connected to it.

    Returns True if the cell was found and removed.
    """
    root = get_root(mxfile, diagram_index)
    removed = False

    # First collect edges connected to this cell
    to_remove = []
    for cell in root.findall("mxCell"):
        cid = cell.get("id", "")
        if cid == cell_id:
            to_remove.append(cell)
            removed = True
        elif cell.get("source") == cell_id or cell.get("target") == cell_id:
            to_remove.append(cell)

    for cell in to_remove:
        root.remove(cell)

    return removed


def update_cell_label(mxfile: ET.Element, cell_id: str, label: str,
                      diagram_index: int = 0) -> bool:
    """Update a cell's label. Returns True if found."""
    cell = find_cell_by_id(mxfile, cell_id, diagram_index)
    if cell is None:
        return False
    cell.set("value", label)
    return True


def move_cell(mxfile: ET.Element, cell_id: str, x: float, y: float,
              diagram_index: int = 0) -> bool:
    """Move a cell to a new position. Returns True if found."""
    cell = find_cell_by_id(mxfile, cell_id, diagram_index)
    if cell is None:
        return False
    geo = cell.find("mxGeometry")
    if geo is None:
        return False
    geo.set("x", str(x))
    geo.set("y", str(y))
    return True


def resize_cell(mxfile: ET.Element, cell_id: str,
                width: float, height: float,
                diagram_index: int = 0) -> bool:
    """Resize a cell. Returns True if found."""
    cell = find_cell_by_id(mxfile, cell_id, diagram_index)
    if cell is None:
        return False
    geo = cell.find("mxGeometry")
    if geo is None:
        return False
    geo.set("width", str(width))
    geo.set("height", str(height))
    return True


# ============================================================================
# Multi-page (diagram) operations
# ============================================================================

def add_page(mxfile: ET.Element, name: str = "",
             page_width: int = 850, page_height: int = 1100) -> str:
    """Add a new diagram page. Returns the diagram ID."""
    existing = mxfile.findall("diagram")
    index = len(existing) + 1
    page_name = name or f"Page-{index}"

    diagram_id = _new_id("diagram")
    diagram = ET.SubElement(mxfile, "diagram")
    diagram.set("id", diagram_id)
    diagram.set("name", page_name)

    model = ET.SubElement(diagram, "mxGraphModel")
    model.set("dx", "1200")
    model.set("dy", "800")
    model.set("grid", "1")
    model.set("gridSize", "10")
    model.set("guides", "1")
    model.set("tooltips", "1")
    model.set("connect", "1")
    model.set("arrows", "1")
    model.set("fold", "1")
    model.set("page", "1")
    model.set("pageScale", "1")
    model.set("pageWidth", str(page_width))
    model.set("pageHeight", str(page_height))
    model.set("math", "0")
    model.set("shadow", "0")

    root = ET.SubElement(model, "root")
    cell0 = ET.SubElement(root, "mxCell")
    cell0.set("id", "0")
    cell1 = ET.SubElement(root, "mxCell")
    cell1.set("id", "1")
    cell1.set("parent", "0")

    return diagram_id


def list_pages(mxfile: ET.Element) -> list[dict]:
    """List all diagram pages."""
    pages = []
    for i, diagram in enumerate(mxfile.findall("diagram")):
        cell_count = len(get_all_cells(mxfile, i))
        pages.append({
            "index": i,
            "id": diagram.get("id", ""),
            "name": diagram.get("name", f"Page-{i+1}"),
            "cell_count": cell_count,
        })
    return pages


def remove_page(mxfile: ET.Element, diagram_index: int) -> bool:
    """Remove a diagram page by index. Cannot remove the last page."""
    diagrams = mxfile.findall("diagram")
    if len(diagrams) <= 1:
        raise RuntimeError("Cannot remove the last page")
    if diagram_index >= len(diagrams):
        raise IndexError(f"Page index {diagram_index} out of range")
    mxfile.remove(diagrams[diagram_index])
    return True


def rename_page(mxfile: ET.Element, diagram_index: int, name: str) -> bool:
    """Rename a diagram page."""
    diagram = get_diagram(mxfile, diagram_index)
    diagram.set("name", name)
    return True
