"""
Macro generation module for the FreeCAD CLI harness.

Generates complete FreeCAD Python macro scripts from JSON project state.
The generated scripts can be executed headlessly via ``FreeCADCmd`` to
create geometry and export to various CAD/mesh formats.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Safe name helper
# ---------------------------------------------------------------------------


def _safe_name(name: str) -> str:
    """Convert a user-supplied name into a valid FreeCAD object label.

    Replaces non-alphanumeric characters with underscores and ensures the
    name does not start with a digit.
    """
    safe = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if safe and safe[0].isdigit():
        safe = f"_{safe}"
    return safe or "Unnamed"


# ---------------------------------------------------------------------------
# Internal generators
# ---------------------------------------------------------------------------


def _gen_header() -> List[str]:
    """Generate import statements and document creation."""
    return [
        "# Auto-generated FreeCAD macro by CLI-Anything FreeCAD harness",
        "import sys",
        "import os",
        "import FreeCAD",
        "import Part",
        "",
        "doc = FreeCAD.newDocument('ExportDoc')",
        "",
    ]


def _gen_parts(project: dict) -> List[str]:
    """Generate Part primitives (Box, Cylinder, Sphere, Cone, Torus)."""
    lines: List[str] = []
    parts = project.get("parts", [])

    for part in parts:
        part_type = part.get("type", "box").lower()
        name = _safe_name(part.get("name", f"Part_{part_type}"))
        props = part.get("params", part.get("properties", {}))

        if part_type == "box":
            length = props.get("length", props.get("Length", 10.0))
            width = props.get("width", props.get("Width", 10.0))
            height = props.get("height", props.get("Height", 10.0))
            lines.append(f"obj_{name} = doc.addObject('Part::Box', '{name}')")
            lines.append(f"obj_{name}.Length = {length}")
            lines.append(f"obj_{name}.Width = {width}")
            lines.append(f"obj_{name}.Height = {height}")

        elif part_type == "cylinder":
            radius = props.get("radius", props.get("Radius", 5.0))
            height = props.get("height", props.get("Height", 10.0))
            lines.append(f"obj_{name} = doc.addObject('Part::Cylinder', '{name}')")
            lines.append(f"obj_{name}.Radius = {radius}")
            lines.append(f"obj_{name}.Height = {height}")

        elif part_type == "sphere":
            radius = props.get("radius", props.get("Radius", 5.0))
            lines.append(f"obj_{name} = doc.addObject('Part::Sphere', '{name}')")
            lines.append(f"obj_{name}.Radius = {radius}")

        elif part_type == "cone":
            radius1 = props.get("radius1", props.get("Radius1", 5.0))
            radius2 = props.get("radius2", props.get("Radius2", 0.0))
            height = props.get("height", props.get("Height", 10.0))
            lines.append(f"obj_{name} = doc.addObject('Part::Cone', '{name}')")
            lines.append(f"obj_{name}.Radius1 = {radius1}")
            lines.append(f"obj_{name}.Radius2 = {radius2}")
            lines.append(f"obj_{name}.Height = {height}")

        elif part_type == "torus":
            radius1 = props.get("radius1", props.get("Radius1", 10.0))
            radius2 = props.get("radius2", props.get("Radius2", 2.0))
            lines.append(f"obj_{name} = doc.addObject('Part::Torus', '{name}')")
            lines.append(f"obj_{name}.Radius1 = {radius1}")
            lines.append(f"obj_{name}.Radius2 = {radius2}")

        else:
            lines.append(f"# WARNING: Unknown part type '{part_type}' for '{name}'")

        lines.append("")

    return lines


def _gen_boolean_ops(project: dict) -> List[str]:
    """Generate boolean operations (Cut, Fuse, Common)."""
    lines: List[str] = []
    boolean_ops = project.get("boolean_ops", [])

    # Map user-friendly names to FreeCAD object types
    op_type_map = {
        "cut": "Part::Cut",
        "subtract": "Part::Cut",
        "fuse": "Part::Fuse",
        "union": "Part::Fuse",
        "common": "Part::Common",
        "intersect": "Part::Common",
        "intersection": "Part::Common",
    }

    for op in boolean_ops:
        op_type = op.get("type", "fuse").lower()
        name = _safe_name(op.get("name", f"BoolOp_{op_type}"))
        base_name = _safe_name(op.get("base", ""))
        tool_name = _safe_name(op.get("tool", ""))
        fc_type = op_type_map.get(op_type, "Part::Fuse")

        lines.append(f"obj_{name} = doc.addObject('{fc_type}', '{name}')")
        lines.append(f"obj_{name}.Base = doc.getObject('{base_name}')")
        lines.append(f"obj_{name}.Tool = doc.getObject('{tool_name}')")
        lines.append("")

    return lines


def _gen_bodies(project: dict) -> List[str]:
    """Generate PartDesign bodies with features (Pad, Pocket, etc.)."""
    lines: List[str] = []
    bodies = project.get("bodies", [])

    if not bodies:
        return lines

    lines.append("import PartDesign")
    lines.append("")

    for body in bodies:
        body_name = _safe_name(body.get("name", "Body"))
        lines.append(
            f"body_{body_name} = doc.addObject('PartDesign::Body', '{body_name}')"
        )

        features = body.get("features", [])
        for feat in features:
            feat_type = feat.get("type", "pad").lower()
            feat_name = _safe_name(feat.get("name", f"Feature_{feat_type}"))
            feat_props = feat.get("properties", {})

            if feat_type == "pad":
                length = feat_props.get("length", feat_props.get("Length", 10.0))
                lines.append(
                    f"feat_{feat_name} = body_{body_name}.newObject("
                    f"'PartDesign::Pad', '{feat_name}')"
                )
                lines.append(f"feat_{feat_name}.Length = {length}")

            elif feat_type == "pocket":
                length = feat_props.get("length", feat_props.get("Length", 5.0))
                lines.append(
                    f"feat_{feat_name} = body_{body_name}.newObject("
                    f"'PartDesign::Pocket', '{feat_name}')"
                )
                lines.append(f"feat_{feat_name}.Length = {length}")

            elif feat_type == "revolution":
                angle = feat_props.get("angle", feat_props.get("Angle", 360.0))
                lines.append(
                    f"feat_{feat_name} = body_{body_name}.newObject("
                    f"'PartDesign::Revolution', '{feat_name}')"
                )
                lines.append(f"feat_{feat_name}.Angle = {angle}")

            elif feat_type == "chamfer":
                size = feat_props.get("size", feat_props.get("Size", 1.0))
                lines.append(
                    f"feat_{feat_name} = body_{body_name}.newObject("
                    f"'PartDesign::Chamfer', '{feat_name}')"
                )
                lines.append(f"feat_{feat_name}.Size = {size}")

            elif feat_type == "fillet":
                radius = feat_props.get("radius", feat_props.get("Radius", 1.0))
                lines.append(
                    f"feat_{feat_name} = body_{body_name}.newObject("
                    f"'PartDesign::Fillet', '{feat_name}')"
                )
                lines.append(f"feat_{feat_name}.Radius = {radius}")

            else:
                lines.append(
                    f"# WARNING: Unknown feature type '{feat_type}' "
                    f"for '{feat_name}'"
                )

            lines.append("")

    return lines


def _gen_placements(project: dict) -> List[str]:
    """Generate placement (position and rotation) commands for parts."""
    lines: List[str] = []
    parts = project.get("parts", [])

    for part in parts:
        name = _safe_name(part.get("name", ""))
        placement = part.get("placement", {})

        if not placement:
            continue

        position = placement.get("position", {})
        rotation = placement.get("rotation", {})

        # Support both list [x, y, z] and dict {"x": ..., "y": ..., "z": ...}
        if isinstance(position, (list, tuple)):
            x = position[0] if len(position) > 0 else 0.0
            y = position[1] if len(position) > 1 else 0.0
            z = position[2] if len(position) > 2 else 0.0
        else:
            x = position.get("x", 0.0)
            y = position.get("y", 0.0)
            z = position.get("z", 0.0)

        # Rotation: support list [rx, ry, rz] (Euler) or dict formats
        if isinstance(rotation, (list, tuple)):
            rx = rotation[0] if len(rotation) > 0 else 0.0
            ry = rotation[1] if len(rotation) > 1 else 0.0
            rz = rotation[2] if len(rotation) > 2 else 0.0
            if rx != 0.0 or ry != 0.0 or rz != 0.0:
                lines.append(
                    f"obj_{name}.Placement = FreeCAD.Placement("
                    f"FreeCAD.Vector({x}, {y}, {z}), "
                    f"FreeCAD.Rotation({rz}, {ry}, {rx}))"
                )
            else:
                lines.append(
                    f"obj_{name}.Placement.Base = FreeCAD.Vector({x}, {y}, {z})"
                )
        elif "axis" in rotation and "angle" in rotation:
            axis = rotation["axis"]
            ax = axis.get("x", 0.0)
            ay = axis.get("y", 0.0)
            az = axis.get("z", 1.0)
            angle = rotation["angle"]
            lines.append(
                f"obj_{name}.Placement = FreeCAD.Placement("
                f"FreeCAD.Vector({x}, {y}, {z}), "
                f"FreeCAD.Rotation(FreeCAD.Vector({ax}, {ay}, {az}), {angle}))"
            )
        elif any(k in rotation for k in ("yaw", "pitch", "roll")):
            yaw = rotation.get("yaw", 0.0)
            pitch = rotation.get("pitch", 0.0)
            roll = rotation.get("roll", 0.0)
            lines.append(
                f"obj_{name}.Placement = FreeCAD.Placement("
                f"FreeCAD.Vector({x}, {y}, {z}), "
                f"FreeCAD.Rotation({yaw}, {pitch}, {roll}))"
            )
        else:
            # Position only, no rotation
            lines.append(
                f"obj_{name}.Placement.Base = FreeCAD.Vector({x}, {y}, {z})"
            )

        lines.append("")

    return lines


def _gen_export(
    project: dict,
    output_path: str,
    export_format: str,
) -> List[str]:
    """Generate export commands for the specified format.

    Supported formats:
      - ``step`` / ``iges``: via ``Part.export()``
      - ``stl``: via ``Mesh.export()``
      - ``obj``: via ``Mesh.export()``
      - ``brep``: via ``Part.export()``
      - ``fcstd``: via ``doc.saveAs()``
    """
    lines: List[str] = []

    # Escape backslashes for Windows paths in the generated Python script
    safe_path = output_path.replace("\\", "/")

    # Recompute the document before exporting
    lines.append("doc.recompute()")
    lines.append("")

    # Collect all visible shape objects for export
    lines.append("# Collect all shape objects for export")
    lines.append("export_objects = []")
    lines.append("for obj in doc.Objects:")
    lines.append("    if hasattr(obj, 'Shape') and obj.Shape.isValid():")
    lines.append("        export_objects.append(obj)")
    lines.append("")

    fmt = export_format.lower()

    if fmt in ("step", "iges", "brep"):
        lines.append(f"Part.export(export_objects, '{safe_path}')")

    elif fmt in ("stl", "obj"):
        lines.append("import Mesh")
        lines.append(f"Mesh.export(export_objects, '{safe_path}')")

    elif fmt == "fcstd":
        lines.append(f"doc.saveAs('{safe_path}')")

    else:
        # Fallback to Part.export for unknown formats
        lines.append(f"# Unknown format '{fmt}', attempting Part.export")
        lines.append(f"Part.export(export_objects, '{safe_path}')")

    lines.append("")
    lines.append("print('Export complete:', os.path.abspath('{safe_path}'))")
    lines.append("")

    return lines


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_macro(
    project: dict,
    output_path: str,
    export_format: str = "step",
) -> str:
    """Generate a complete FreeCAD Python macro script from project state.

    The generated script, when executed by ``FreeCADCmd``, will:
      1. Create a new FreeCAD document.
      2. Add all parts/primitives defined in the project.
      3. Apply boolean operations.
      4. Create PartDesign bodies with features.
      5. Set placements (positions and rotations).
      6. Export to the requested format.

    Parameters
    ----------
    project : dict
        Project JSON state.  Expected top-level keys:

        - ``parts``: list of part definitions (type, name, properties,
          placement).
        - ``boolean_ops``: list of boolean operation definitions.
        - ``bodies``: list of PartDesign body definitions with features.

    output_path : str
        Destination file path for the export.
    export_format : str
        Target format: ``"step"``, ``"iges"``, ``"stl"``, ``"obj"``,
        ``"brep"``, or ``"fcstd"``.

    Returns
    -------
    str
        Complete Python macro script ready for execution by FreeCADCmd.
    """
    sections: List[List[str]] = [
        _gen_header(),
        _gen_parts(project),
        _gen_boolean_ops(project),
        _gen_bodies(project),
        _gen_placements(project),
        _gen_export(project, output_path, export_format),
    ]

    # Flatten all sections and join with newlines
    all_lines: List[str] = []
    for section in sections:
        all_lines.extend(section)

    return "\n".join(all_lines)
