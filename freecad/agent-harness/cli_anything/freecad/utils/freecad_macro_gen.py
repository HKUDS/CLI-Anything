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


# Names FreeCAD creates inside PartDesign::Body.setupObject, in creation order:
# App::Origin "Origin", then Origin::setupObject axes and planes.
_BODY_ORIGIN_OBJECT_NAMES = (
    "Origin",
    "X_Axis",
    "Y_Axis",
    "Z_Axis",
    "XY_Plane",
    "XZ_Plane",
    "YZ_Plane",
)


def _increment_numeric_suffix(suffix: str) -> str:
    """Increment a digit string the way ``Base::Tools::string_comp::increment`` does."""
    if not suffix:
        return "1"
    digits = list(suffix)
    carry = 1
    for index in range(len(digits) - 1, -1, -1):
        if carry == 0:
            break
        total = (ord(digits[index]) - 48) + carry
        digits[index] = chr((total % 10) + 48)
        carry = total // 10
    if carry:
        digits.insert(0, chr(carry + 48))
    return "".join(digits)


def _numeric_suffix_greater(candidate: str, current: str) -> bool:
    """Return True if *candidate* is the higher FreeCAD numeric suffix."""
    if not current:
        return True
    if len(candidate) != len(current):
        return len(candidate) > len(current)
    return candidate > current


def _freecad_unique_name(name: str, used: set[str]) -> str:
    """Return the internal name ``Document.getUniqueObjectName`` would assign.

    An unused name is kept. A collision drops trailing digits (so ``Box001``
    does not become ``Box001001``) and then takes the next zero-padded suffix
    from ``Base::Tools::getUniqueName`` with a width of 3. Already-taken
    candidates are skipped so the string passed to ``addObject`` is the label
    FreeCAD stores on the object.
    """
    if name not in used:
        return name

    # Document::getUniqueObjectName strips trailing digits unless
    # KeepTrailingDigits is set. The default document does not set it.
    end = len(name)
    while end > 0 and name[end - 1].isdigit():
        end -= 1
    if 0 < end < len(name):
        name = name[:end]

    highest = ""
    for existing in used:
        if not existing.startswith(name):
            continue
        suffix = existing[len(name):]
        if suffix.isdigit() and _numeric_suffix_greater(suffix, highest):
            highest = suffix

    incremented = _increment_numeric_suffix(highest).zfill(3)
    candidate = f"{name}{incremented}"
    while candidate in used:
        incremented = _increment_numeric_suffix(incremented).zfill(3)
        candidate = f"{name}{incremented}"
    return candidate


class _FreeCADNameAllocator:
    """Allocate FreeCAD object names in the order the macro creates them.

    Sections of one script must share a single allocator. ``Box A`` and
    ``Box-A`` both sanitize to ``Box_A``; FreeCAD then labels the second
    object ``Box_A001``. Tracking that suffix keeps later references and
    the export filter pointed at every solid.
    """

    def __init__(self) -> None:
        self._used: set[str] = set()
        self.part_labels: Dict[Any, str] = {}
        self.sketch_labels: Dict[int, str] = {}
        self.body_labels: Dict[int, str] = {}

    def allocate(self, raw_name: str) -> str:
        """Reserve and return the unique label for *raw_name*."""
        unique = _freecad_unique_name(_safe_name(raw_name), self._used)
        self._used.add(unique)
        return unique

    def reserve_body_origin(self) -> None:
        """Reserve the Origin, axes, and planes created with a PartDesign body."""
        for raw_name in _BODY_ORIGIN_OBJECT_NAMES:
            self.allocate(raw_name)

    def remember_part(self, part_id: Any, label: str) -> None:
        """Record the label assigned to a project part id."""
        if part_id is not None:
            self.part_labels[part_id] = label

    def part_var(self, part_id: Any) -> Optional[str]:
        """Return the Python variable for a previously allocated part."""
        label = self.part_labels.get(part_id)
        if label is None:
            return None
        return f"obj_{label}"


def _construction_arg(elem: Dict[str, Any]) -> str:
    """Return the ``addGeometry`` construction flag for a sketch element."""
    return "True" if elem.get("construction") else "False"


def _part_object_var(
    project: dict,
    names: "_FreeCADNameAllocator",
    part_id: Any,
) -> str:
    """Resolve a part id to the Python variable emitted for that object."""
    recorded = names.part_var(part_id)
    if recorded is not None:
        return recorded
    part = _part_by_id(project, part_id)
    if part is None:
        return "None"
    return f"obj_{_safe_name(part.get('name', 'Part'))}"


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


_RENDERABLE_PRIMITIVES = {"box", "cylinder", "sphere", "cone", "torus"}


def _emit_primitive(lines: List[str], part_type: str, name: str, props: Dict[str, Any]) -> bool:
    """Append FreeCAD object creation lines for a supported primitive."""
    if part_type == "box":
        length = props.get("length", props.get("Length", 10.0))
        width = props.get("width", props.get("Width", 10.0))
        height = props.get("height", props.get("Height", 10.0))
        lines.append(f"obj_{name} = doc.addObject('Part::Box', '{name}')")
        lines.append(f"obj_{name}.Length = {length}")
        lines.append(f"obj_{name}.Width = {width}")
        lines.append(f"obj_{name}.Height = {height}")
        return True

    if part_type == "cylinder":
        radius = props.get("radius", props.get("Radius", 5.0))
        height = props.get("height", props.get("Height", 10.0))
        lines.append(f"obj_{name} = doc.addObject('Part::Cylinder', '{name}')")
        lines.append(f"obj_{name}.Radius = {radius}")
        lines.append(f"obj_{name}.Height = {height}")
        return True

    if part_type == "sphere":
        radius = props.get("radius", props.get("Radius", 5.0))
        lines.append(f"obj_{name} = doc.addObject('Part::Sphere', '{name}')")
        lines.append(f"obj_{name}.Radius = {radius}")
        return True

    if part_type == "cone":
        radius1 = props.get("radius1", props.get("Radius1", 5.0))
        radius2 = props.get("radius2", props.get("Radius2", 0.0))
        height = props.get("height", props.get("Height", 10.0))
        lines.append(f"obj_{name} = doc.addObject('Part::Cone', '{name}')")
        lines.append(f"obj_{name}.Radius1 = {radius1}")
        lines.append(f"obj_{name}.Radius2 = {radius2}")
        lines.append(f"obj_{name}.Height = {height}")
        return True

    if part_type == "torus":
        radius1 = props.get("radius1", props.get("Radius1", 10.0))
        radius2 = props.get("radius2", props.get("Radius2", 2.0))
        lines.append(f"obj_{name} = doc.addObject('Part::Torus', '{name}')")
        lines.append(f"obj_{name}.Radius1 = {radius1}")
        lines.append(f"obj_{name}.Radius2 = {radius2}")
        return True

    return False


def _part_by_id(project: dict, part_id: Any) -> Optional[Dict[str, Any]]:
    """Return the part payload matching *part_id*, if present."""
    for part in project.get("parts", []):
        if part.get("id") == part_id:
            return part
    return None


def _mirrored_position(position: Any, plane: str) -> List[float]:
    """Return a mirrored position vector for a simple plane reflection."""
    if isinstance(position, (list, tuple)):
        coords = [float(position[idx]) if len(position) > idx else 0.0 for idx in range(3)]
    else:
        coords = [
            float(position.get("x", 0.0)),
            float(position.get("y", 0.0)),
            float(position.get("z", 0.0)),
        ]
    axis_index = {"YZ": 0, "XZ": 1, "XY": 2}.get(plane.upper())
    if axis_index is not None:
        coords[axis_index] *= -1.0
    return coords


def _mirror_render_spec(project: dict, part: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Resolve a mirrored part into a renderable primitive approximation."""
    params = part.get("params", {})
    original = _part_by_id(project, params.get("original_id"))
    if not original:
        return None
    original_type = str(original.get("type", "")).lower()
    if original_type not in _RENDERABLE_PRIMITIVES:
        return None

    placement = dict(original.get("placement") or {})
    placement["position"] = _mirrored_position(
        placement.get("position") or [0.0, 0.0, 0.0],
        str(params.get("mirror_plane", "XZ")),
    )
    return {
        "type": original_type,
        "params": dict(original.get("params") or {}),
        "placement": placement,
    }


def _render_spec_for_part(project: dict, part: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the renderable primitive spec for *part*, if supported."""
    part_type = str(part.get("type", "")).lower()
    if part_type in _RENDERABLE_PRIMITIVES:
        return {
            "type": part_type,
            "params": dict(part.get("params") or {}),
            "placement": dict(part.get("placement") or {}),
        }
    if part_type == "mirror":
        return _mirror_render_spec(project, part)
    return None


def _gen_parts(
    project: dict,
    names: Optional[_FreeCADNameAllocator] = None,
) -> List[str]:
    """Generate Part primitives (Box, Cylinder, Sphere, Cone, Torus)."""
    lines: List[str] = []
    parts = project.get("parts", [])
    if names is None:
        names = _FreeCADNameAllocator()

    # Boolean operation types that should be handled by _gen_boolean_ops
    boolean_types = {"cut", "subtract", "fuse", "union", "common", "intersect", "intersection"}

    for part in parts:
        part_type = str(part.get("type", "box")).lower()

        # Skip boolean operations - they're handled separately
        if part_type in boolean_types:
            continue

        raw_name = part.get("name", f"Part_{part_type}")
        render_spec = _render_spec_for_part(project, part)
        if render_spec is None:
            lines.append(
                f"# WARNING: Unknown part type '{part_type}' for '{_safe_name(raw_name)}'"
            )
            lines.append("")
            continue

        label = names.allocate(raw_name)
        names.remember_part(part.get("id"), label)
        props = render_spec["params"]
        if not _emit_primitive(lines, render_spec["type"], label, props):
            lines.append(f"# WARNING: Unknown part type '{part_type}' for '{label}'")

        lines.append("")

    return lines


def _gen_sketches(
    project: dict,
    names: Optional[_FreeCADNameAllocator] = None,
) -> List[str]:
    """Generate Sketcher sketches with geometry and constraints."""
    lines: List[str] = []
    sketches = project.get("sketches", [])
    if names is None:
        names = _FreeCADNameAllocator()

    if not sketches:
        return lines

    lines.append("import Sketcher")
    lines.append("")

    # Plane mapping
    plane_map = {
        "XY": ("XY_Plane", "XY"),
        "XZ": ("XZ_Plane", "XZ"),
        "YZ": ("YZ_Plane", "YZ"),
    }

    for sketch_index, sketch in enumerate(sketches):
        sketch_name = names.allocate(sketch.get("name", "Sketch"))
        names.sketch_labels[sketch_index] = sketch_name
        sketch_var = f"sketch_{sketch_name}"
        plane = sketch.get("plane", "XY")
        offset = sketch.get("offset", 0.0)

        # Create sketch object
        lines.append(f"{sketch_var} = doc.addObject('Sketcher::SketchObject', '{sketch_name}')")

        # Attach to plane
        plane_ref, plane_mode = plane_map.get(plane, ("XY_Plane", "XY"))
        lines.append(f"{sketch_var}.MapMode = 'FlatFace'")

        # Set placement based on plane and offset
        if plane == "XY":
            lines.append(f"{sketch_var}.Placement = FreeCAD.Placement(FreeCAD.Vector(0,0,{offset}), FreeCAD.Rotation(0,0,0))")
        elif plane == "XZ":
            lines.append(f"{sketch_var}.Placement = FreeCAD.Placement(FreeCAD.Vector(0,{offset},0), FreeCAD.Rotation(90,0,0))")
        elif plane == "YZ":
            lines.append(f"{sketch_var}.Placement = FreeCAD.Placement(FreeCAD.Vector({offset},0,0), FreeCAD.Rotation(0,90,0))")

        # Add geometry elements
        elements = sketch.get("elements", [])
        for elem in elements:
            elem_type = elem.get("type", "").lower()
            construction = _construction_arg(elem)

            if elem_type == "line":
                start = elem.get("start", [0, 0])
                end = elem.get("end", [10, 10])
                lines.append(f"{sketch_var}.addGeometry(Part.LineSegment(")
                lines.append(f"    FreeCAD.Vector({start[0]},{start[1]},0),")
                lines.append(f"    FreeCAD.Vector({end[0]},{end[1]},0)")
                lines.append(f"), {construction})")

            elif elem_type == "circle":
                center = elem.get("center", [0, 0])
                radius = elem.get("radius", 10)
                lines.append(f"{sketch_var}.addGeometry(Part.Circle(")
                lines.append(f"    FreeCAD.Vector({center[0]},{center[1]},0),")
                lines.append(f"    FreeCAD.Vector(0,0,1),")
                lines.append(f"    {radius}")
                lines.append(f"), {construction})")

            elif elem_type == "rectangle":
                corner = elem.get("corner", [0, 0])
                width = elem.get("width", 10)
                height = elem.get("height", 10)
                x, y = corner[0], corner[1]
                # Rectangle as 4 lines
                lines.append(f"# Rectangle at ({x},{y}) with width={width}, height={height}")
                lines.append(f"{sketch_var}.addGeometry(Part.LineSegment(FreeCAD.Vector({x},{y},0), FreeCAD.Vector({x+width},{y},0)), {construction})")
                lines.append(f"{sketch_var}.addGeometry(Part.LineSegment(FreeCAD.Vector({x+width},{y},0), FreeCAD.Vector({x+width},{y+height},0)), {construction})")
                lines.append(f"{sketch_var}.addGeometry(Part.LineSegment(FreeCAD.Vector({x+width},{y+height},0), FreeCAD.Vector({x},{y+height},0)), {construction})")
                lines.append(f"{sketch_var}.addGeometry(Part.LineSegment(FreeCAD.Vector({x},{y+height},0), FreeCAD.Vector({x},{y},0)), {construction})")

            elif elem_type == "polygon":
                center = elem.get("center", [0, 0])
                sides = elem.get("sides", 6)
                radius = elem.get("radius", 10)
                import math
                lines.append(f"# Polygon with {sides} sides")
                lines.append(f"import math")
                for i in range(sides):
                    angle1 = 2 * 3.14159265359 * i / sides
                    angle2 = 2 * 3.14159265359 * (i + 1) / sides
                    x1 = center[0] + radius * math.cos(angle1)
                    y1 = center[1] + radius * math.sin(angle1)
                    x2 = center[0] + radius * math.cos(angle2)
                    y2 = center[1] + radius * math.sin(angle2)
                    lines.append(f"{sketch_var}.addGeometry(Part.LineSegment(FreeCAD.Vector({x1:.6f},{y1:.6f},0), FreeCAD.Vector({x2:.6f},{y2:.6f},0)), {construction})")

        lines.append("")

    return lines


def _gen_boolean_ops(
    project: dict,
    names: Optional[_FreeCADNameAllocator] = None,
) -> List[str]:
    """Generate boolean operations (Cut, Fuse, Common)."""
    lines: List[str] = []
    if names is None:
        names = _FreeCADNameAllocator()

    # Extract boolean operations from parts array
    parts = project.get("parts", [])
    boolean_types = {"cut", "subtract", "fuse", "union", "common", "intersect", "intersection"}
    boolean_ops = [p for p in parts if str(p.get("type", "")).lower() in boolean_types]

    if not boolean_ops:
        return lines

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
        params = op.get("params", {})
        base_id = params.get("base_id")
        tool_id = params.get("tool_id")
        fc_type = op_type_map.get(op_type, "Part::Fuse")

        # Resolve operands before reserving this result's name. An invalid
        # operation does not create a document object, so it must not consume
        # a FreeCAD label.
        base_var = _part_object_var(project, names, base_id)
        tool_var = _part_object_var(project, names, tool_id)
        raw_label = _safe_name(op.get("name", f"BoolOp_{op_type}"))
        if base_var == "None" or tool_var == "None":
            lines.append(f"# WARNING: Boolean operation {raw_label} has invalid base or tool ID")
            continue

        label = names.allocate(op.get("name", f"BoolOp_{op_type}"))
        names.remember_part(op.get("id"), label)
        lines.append(f"obj_{label} = doc.addObject('{fc_type}', '{label}')")
        lines.append(f"obj_{label}.Base = {base_var}")
        lines.append(f"obj_{label}.Tool = {tool_var}")
        lines.append("")

    return lines


def _placement_expr(placement: Optional[Dict[str, Any]]) -> Optional[str]:
    """Return a FreeCAD placement expression for a stored placement payload."""
    if not placement:
        return None
    position = placement.get("position") or [0.0, 0.0, 0.0]
    rotation = placement.get("rotation") or [0.0, 0.0, 0.0]
    x = float(position[0] if len(position) > 0 else 0.0)
    y = float(position[1] if len(position) > 1 else 0.0)
    z = float(position[2] if len(position) > 2 else 0.0)
    rx = float(rotation[0] if len(rotation) > 0 else 0.0)
    ry = float(rotation[1] if len(rotation) > 1 else 0.0)
    rz = float(rotation[2] if len(rotation) > 2 else 0.0)
    return (
        "FreeCAD.Placement("
        f"FreeCAD.Vector({x}, {y}, {z}), "
        f"FreeCAD.Rotation({rz}, {ry}, {rx}))"
    )


def _dominant_axis(direction: Any) -> tuple[str, bool, bool]:
    """Resolve a direction vector to the closest body-origin axis."""
    if not isinstance(direction, (list, tuple)) or len(direction) != 3:
        return ("X", False, False)
    values = [float(component) for component in direction]
    axis_index = max(range(3), key=lambda idx: abs(values[idx]))
    axis_name = "XYZ"[axis_index]
    reversed_axis = values[axis_index] < 0
    off_axis = any(abs(value) > 1e-9 for idx, value in enumerate(values) if idx != axis_index)
    return (axis_name, reversed_axis, off_axis)


def _gen_bodies(
    project: dict,
    names: Optional[_FreeCADNameAllocator] = None,
) -> List[str]:
    """Generate PartDesign bodies with primitive and pattern features."""
    lines: List[str] = []
    bodies = project.get("bodies", [])
    if names is None:
        names = _FreeCADNameAllocator()

    if not bodies:
        return lines

    lines.append("import PartDesign")
    lines.append("")
    lines.extend(
        [
            "def _body_origin_ref(body_obj, role):",
            "    for origin_obj in body_obj.Origin.OriginFeatures:",
            "        if getattr(origin_obj, 'Role', None) == role:",
            "            return origin_obj",
            "    raise RuntimeError(f'Could not resolve body origin role: {role}')",
            "",
        ]
    )

    for body_index, body in enumerate(bodies):
        body_name = names.allocate(body.get("name", "Body"))
        names.body_labels[body_index] = body_name
        names.reserve_body_origin()
        body_var = f"body_{body_name}"
        lines.append(f"{body_var} = doc.addObject('PartDesign::Body', '{body_name}')")

        features = body.get("features", [])
        previous_var: Optional[str] = None
        feature_counter = 0

        def emit_pattern(
            pattern_type: str,
            pattern_payload: Dict[str, Any],
            source_var: Optional[str],
            suffix: Optional[str] = None,
        ) -> Optional[str]:
            nonlocal feature_counter
            if source_var is None:
                lines.append(f"# WARNING: Cannot add {pattern_type} without a previous body feature")
                return None
            feature_counter += 1
            pattern_var = f"feat_{body_name}_{feature_counter}_{pattern_type}"
            if pattern_type == "linear_pattern":
                label = names.allocate(f"{pattern_type}_{feature_counter}")
                axis, reversed_axis, off_axis = _dominant_axis(pattern_payload.get("direction"))
                lines.append(
                    f"{pattern_var} = {body_var}.newObject('PartDesign::LinearPattern', '{label}')"
                )
                lines.append(f"{pattern_var}.Originals = [{source_var}]")
                lines.append(
                    f"{pattern_var}.Direction = (_body_origin_ref({body_var}, '{axis}_Axis'), [''])"
                )
                lines.append(f"{pattern_var}.Length = {float(pattern_payload.get('length', 50.0))}")
                lines.append(
                    f"{pattern_var}.Occurrences = {int(pattern_payload.get('occurrences', 3))}"
                )
                if reversed_axis:
                    lines.append(f"{pattern_var}.Reversed = True")
                if off_axis:
                    lines.append(
                        f"# WARNING: Non-axis-aligned direction {pattern_payload.get('direction')} "
                        f"collapsed to dominant {axis}-axis"
                    )
            elif pattern_type == "polar_pattern":
                label = names.allocate(f"{pattern_type}_{feature_counter}")
                axis = str(pattern_payload.get("axis", "Z")).upper()
                lines.append(
                    f"{pattern_var} = {body_var}.newObject('PartDesign::PolarPattern', '{label}')"
                )
                lines.append(f"{pattern_var}.Originals = [{source_var}]")
                lines.append(
                    f"{pattern_var}.Axis = (_body_origin_ref({body_var}, '{axis}_Axis'), [''])"
                )
                lines.append(f"{pattern_var}.Angle = {float(pattern_payload.get('angle', 360.0))}")
                lines.append(
                    f"{pattern_var}.Occurrences = {int(pattern_payload.get('occurrences', 4))}"
                )
            elif pattern_type == "mirrored":
                label = names.allocate(f"{pattern_type}_{feature_counter}")
                plane = str(pattern_payload.get("plane", "XY")).upper()
                lines.append(
                    f"{pattern_var} = {body_var}.newObject('PartDesign::Mirrored', '{label}')"
                )
                lines.append(f"{pattern_var}.Originals = [{source_var}]")
                lines.append(
                    f"{pattern_var}.MirrorPlane = (_body_origin_ref({body_var}, '{plane}_Plane'), [''])"
                )
            else:
                lines.append(f"# WARNING: Unknown pattern type '{pattern_type}' in {suffix or 'feature'}")
                return source_var
            lines.append("")
            return pattern_var

        primitive_map = {
            "additive_box": ("PartDesign::AdditiveBox", ("Length", "length"), ("Width", "width"), ("Height", "height")),
            "additive_cylinder": ("PartDesign::AdditiveCylinder", ("Radius", "radius"), ("Height", "height")),
            "additive_sphere": ("PartDesign::AdditiveSphere", ("Radius", "radius")),
            "additive_cone": ("PartDesign::AdditiveCone", ("Radius1", "radius1"), ("Radius2", "radius2"), ("Height", "height")),
            "additive_torus": ("PartDesign::AdditiveTorus", ("Radius1", "radius1"), ("Radius2", "radius2")),
            "additive_wedge": ("PartDesign::AdditiveWedge", ("Xmin", "xmin"), ("Xmax", "xmax"), ("Ymin", "ymin"), ("Ymax", "ymax"), ("Zmin", "zmin"), ("Zmax", "zmax"), ("X2min", "x2min"), ("X2max", "x2max"), ("Z2min", "z2min"), ("Z2max", "z2max")),
            "subtractive_box": ("PartDesign::SubtractiveBox", ("Length", "length"), ("Width", "width"), ("Height", "height")),
            "subtractive_cylinder": ("PartDesign::SubtractiveCylinder", ("Radius", "radius"), ("Height", "height")),
            "subtractive_sphere": ("PartDesign::SubtractiveSphere", ("Radius", "radius")),
            "subtractive_cone": ("PartDesign::SubtractiveCone", ("Radius1", "radius1"), ("Radius2", "radius2"), ("Height", "height")),
            "subtractive_torus": ("PartDesign::SubtractiveTorus", ("Radius1", "radius1"), ("Radius2", "radius2")),
            "subtractive_wedge": ("PartDesign::SubtractiveWedge", ("Xmin", "xmin"), ("Xmax", "xmax"), ("Ymin", "ymin"), ("Ymax", "ymax"), ("Zmin", "zmin"), ("Zmax", "zmax"), ("X2min", "x2min"), ("X2max", "x2max"), ("Z2min", "z2min"), ("Z2max", "z2max")),
        }

        for feat in features:
            feat_type = feat.get("type", "pad").lower()
            raw_feat_name = feat.get("name", f"Feature_{feat_type}")
            feat_props = feat.get("properties", {})
            feature_counter += 1
            feat_var = f"feat_{body_name}_{feature_counter}_{_safe_name(feat_type)}"

            if feat_type in primitive_map:
                feat_name = names.allocate(raw_feat_name)
                class_name, *prop_pairs = primitive_map[feat_type]
                lines.append(f"{feat_var} = {body_var}.newObject('{class_name}', '{feat_name}')")
                for prop_name, key in prop_pairs:
                    value = feat.get(key, feat_props.get(key))
                    if value is not None:
                        lines.append(f"{feat_var}.{prop_name} = {float(value)}")
                placement_expr = _placement_expr(feat.get("placement") or feat_props.get("placement"))
                if placement_expr:
                    lines.append(f"{feat_var}.Placement = {placement_expr}")
                previous_var = feat_var

            elif feat_type == "linear_pattern":
                previous_var = emit_pattern("linear_pattern", feat, previous_var)

            elif feat_type == "polar_pattern":
                previous_var = emit_pattern("polar_pattern", feat, previous_var)

            elif feat_type == "mirrored":
                previous_var = emit_pattern("mirrored", feat, previous_var)

            elif feat_type == "multi_transform":
                transforms = feat.get("transformations", [])
                if not transforms:
                    lines.append(
                        f"# WARNING: multi_transform '{_safe_name(raw_feat_name)}' has no transformations"
                    )
                for transform_index, transform in enumerate(transforms):
                    previous_var = emit_pattern(
                        str(transform.get("type", "")).lower(),
                        transform,
                        previous_var,
                        suffix=f"multi_transform[{transform_index}]",
                    )

            elif feat_type == "pad":
                feat_name = names.allocate(raw_feat_name)
                sketch_index = feat.get("sketch_index")
                length = feat.get("length", feat_props.get("length", feat_props.get("Length", 10.0)))

                lines.append(
                    f"{feat_var} = {body_var}.newObject('PartDesign::Pad', '{feat_name}')"
                )

                # Link to sketch if sketch_index is provided
                if sketch_index is not None:
                    sketches = project.get("sketches", [])
                    if sketch_index < len(sketches):
                        sketch_name = names.sketch_labels.get(sketch_index)
                        if sketch_name is None:
                            sketch_obj = sketches[sketch_index]
                            sketch_name = _safe_name(sketch_obj.get("name", "Sketch"))
                        sketch_var = f"sketch_{sketch_name}"
                        lines.append(f"{feat_var}.Profile = {sketch_var}")

                lines.append(f"{feat_var}.Length = {length}")
                previous_var = feat_var

            elif feat_type == "pocket":
                feat_name = names.allocate(raw_feat_name)
                length = feat_props.get("length", feat_props.get("Length", 5.0))
                lines.append(
                    f"{feat_var} = {body_var}.newObject('PartDesign::Pocket', '{feat_name}')"
                )
                lines.append(f"{feat_var}.Length = {length}")
                previous_var = feat_var

            elif feat_type == "revolution":
                feat_name = names.allocate(raw_feat_name)
                angle = feat_props.get("angle", feat_props.get("Angle", 360.0))
                lines.append(
                    f"{feat_var} = {body_var}.newObject('PartDesign::Revolution', '{feat_name}')"
                )
                lines.append(f"{feat_var}.Angle = {angle}")
                previous_var = feat_var

            elif feat_type == "chamfer":
                feat_name = names.allocate(raw_feat_name)
                size = feat_props.get("size", feat_props.get("Size", 1.0))
                lines.append(
                    f"{feat_var} = {body_var}.newObject('PartDesign::Chamfer', '{feat_name}')"
                )
                lines.append(f"{feat_var}.Size = {size}")
                previous_var = feat_var

            elif feat_type == "fillet":
                feat_name = names.allocate(raw_feat_name)
                radius = feat_props.get("radius", feat_props.get("Radius", 1.0))
                lines.append(
                    f"{feat_var} = {body_var}.newObject('PartDesign::Fillet', '{feat_name}')"
                )
                lines.append(f"{feat_var}.Radius = {radius}")
                previous_var = feat_var

            else:
                lines.append(
                    f"# WARNING: Unknown feature type '{feat_type}' "
                    f"for '{_safe_name(raw_feat_name)}'"
                )

            lines.append("")

    return lines


def _gen_placements(
    project: dict,
    names: Optional[_FreeCADNameAllocator] = None,
) -> List[str]:
    """Generate placement (position and rotation) commands for parts."""
    lines: List[str] = []
    parts = project.get("parts", [])
    if names is None:
        names = _FreeCADNameAllocator()

    for part in parts:
        recorded = names.part_var(part.get("id"))
        if recorded is not None:
            var = recorded
            display = recorded[len("obj_"):]
        else:
            display = _safe_name(part.get("name", ""))
            var = f"obj_{display}"
        render_spec = _render_spec_for_part(project, part)
        if render_spec is None:
            lines.append(f"# WARNING: Skipping placement for unsupported part '{display}'")
            lines.append("")
            continue
        placement = render_spec.get("placement", {})

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
                    f"{var}.Placement = FreeCAD.Placement("
                    f"FreeCAD.Vector({x}, {y}, {z}), "
                    f"FreeCAD.Rotation({rz}, {ry}, {rx}))"
                )
            else:
                lines.append(
                    f"{var}.Placement.Base = FreeCAD.Vector({x}, {y}, {z})"
                )
        elif "axis" in rotation and "angle" in rotation:
            axis = rotation["axis"]
            ax = axis.get("x", 0.0)
            ay = axis.get("y", 0.0)
            az = axis.get("z", 1.0)
            angle = rotation["angle"]
            lines.append(
                f"{var}.Placement = FreeCAD.Placement("
                f"FreeCAD.Vector({x}, {y}, {z}), "
                f"FreeCAD.Rotation(FreeCAD.Vector({ax}, {ay}, {az}), {angle}))"
            )
        elif any(k in rotation for k in ("yaw", "pitch", "roll")):
            yaw = rotation.get("yaw", 0.0)
            pitch = rotation.get("pitch", 0.0)
            roll = rotation.get("roll", 0.0)
            lines.append(
                f"{var}.Placement = FreeCAD.Placement("
                f"FreeCAD.Vector({x}, {y}, {z}), "
                f"FreeCAD.Rotation({yaw}, {pitch}, {roll}))"
            )
        else:
            # Position only, no rotation
            lines.append(
                f"{var}.Placement.Base = FreeCAD.Vector({x}, {y}, {z})"
            )

        lines.append("")

    return lines


def _gen_export(
    project: dict,
    output_path: str,
    export_format: str,
    names: Optional[_FreeCADNameAllocator] = None,
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

    # Collect only visible shape objects for export.
    # "Box A" and "Box-A" both sanitize to Box_A. FreeCAD then labels the
    # second solid Box_A001, so a set of normalized names drops it. Export
    # the Python objects created for the resolved labels instead.
    lines.append("# Collect visible shape objects for export")
    lines.append("export_objects = []")

    parts = project.get("parts", [])
    bodies = project.get("bodies", [])
    if names is None:
        names = _FreeCADNameAllocator()

    export_vars: List[str] = []
    visible_labels: List[str] = []

    def _add_export(var: Optional[str], label: Optional[str]) -> None:
        if var and var not in export_vars:
            export_vars.append(var)
        if label and label not in visible_labels:
            visible_labels.append(label)

    tracked = bool(names.part_labels or names.body_labels)
    if tracked:
        for part in parts:
            if not part.get("visible", True):
                continue
            label = names.part_labels.get(part.get("id"))
            _add_export(names.part_var(part.get("id")), label)
        for body_index, _body in enumerate(bodies):
            label = names.body_labels.get(body_index)
            if label:
                _add_export(f"body_{label}", label)
    else:
        for part in parts:
            if not part.get("visible", True):
                continue
            part_type = str(part.get("type", "unknown")).lower()
            label = _safe_name(part.get("name", f"Part_{part_type}"))
            _add_export(None, label)
        for body in bodies:
            _add_export(None, _safe_name(body.get("name", "Body")))

    if export_vars:
        rendered_vars = ", ".join(export_vars)
        rendered_labels = ", ".join(visible_labels)
        lines.append(f"# Resolved FreeCAD labels: {rendered_labels}")
        lines.append(f"_export_candidates = [{rendered_vars}]")
        lines.append("for obj in _export_candidates:")
        lines.append("    if hasattr(obj, 'Shape') and obj.Shape.isValid():")
        lines.append("        export_objects.append(obj)")
    elif visible_labels:
        rendered_labels = ", ".join(f"'{name}'" for name in visible_labels)
        lines.append("# Only export visible objects")
        lines.append(f"visible_names = {{{rendered_labels}}}")
        lines.append("for obj in doc.Objects:")
        lines.append("    if hasattr(obj, 'Shape') and obj.Shape.isValid():")
        lines.append("        if obj.Label in visible_names:")
        lines.append("            export_objects.append(obj)")
    else:
        # If no visible names specified, export all valid shapes
        lines.append("# Export all valid shapes")
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
    lines.append(f"print('Export complete:', os.path.abspath('{safe_path}'))")
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
    # One allocator so object creation, placements, and the export filter
    # share the labels FreeCAD will store, including 001-style suffixes.
    names = _FreeCADNameAllocator()
    sections: List[List[str]] = [
        _gen_header(),
        _gen_sketches(project, names),
        _gen_parts(project, names),
        _gen_boolean_ops(project, names),
        _gen_bodies(project, names),
        _gen_placements(project, names),
        _gen_export(project, output_path, export_format, names),
    ]

    # Flatten all sections and join with newlines
    all_lines: List[str] = []
    for section in sections:
        all_lines.extend(section)

    return "\n".join(all_lines)
