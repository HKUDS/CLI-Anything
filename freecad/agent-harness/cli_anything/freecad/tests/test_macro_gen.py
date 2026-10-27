"""Macro-generation regressions that do not require FreeCAD.

Covers the two export/geometry bugs reported on PR 422:
normalized names that collide must both be exported, and sketch
construction geometry must be passed through to ``addGeometry``.
"""

from __future__ import annotations

import ast
import re

from cli_anything.freecad.core.body import additive_box, create_body, pad
from cli_anything.freecad.core.document import create_document
from cli_anything.freecad.core.motion import _generate_motion_macro
from cli_anything.freecad.core.parts import add_part, boolean_op
from cli_anything.freecad.core.preview import _generate_preview_macro
from cli_anything.freecad.core.sketch import (
    add_circle,
    add_rectangle,
    create_sketch,
    set_construction,
)
from cli_anything.freecad.utils.freecad_macro_gen import (
    _freecad_unique_name,
    generate_macro,
)


def _visible_labels(macro: str) -> list[str]:
    match = re.search(r"^# Resolved FreeCAD labels: (.+)$", macro, re.MULTILINE)
    assert match, f"export label comment missing:\n{macro}"
    return [label for label in match.group(1).split(", ") if label]


def _export_candidates(macro: str) -> list[str]:
    match = re.search(r"^_export_candidates = \[(.+)\]$", macro, re.MULTILINE)
    assert match, f"export candidate list missing:\n{macro}"
    return [item.strip() for item in match.group(1).split(",") if item.strip()]


def test_freecad_unique_name_uses_three_digit_suffixes():
    """FreeCAD labels the second Box_A as Box_A001, then Box_A002."""
    used: set[str] = set()
    first = _freecad_unique_name("Box_A", used)
    used.add(first)
    second = _freecad_unique_name("Box_A", used)
    used.add(second)
    third = _freecad_unique_name("Box_A", used)
    assert first == "Box_A"
    assert second == "Box_A001"
    assert third == "Box_A002"
    assert _freecad_unique_name("Box", used) == "Box"
    # An explicit Box_A001 is kept while that label is free, and the next
    # collision reuses the Box_A sequence instead of producing Box_A001001.
    assert _freecad_unique_name("Box_A001", {"Box_A"}) == "Box_A001"
    assert _freecad_unique_name("Box_A001", {first, second}) == "Box_A002"


def test_normalized_name_collision_keeps_every_visible_part(tmp_path):
    """Box A and Box-A both sanitize to Box_A but must both be exported."""
    project = create_document()
    add_part(
        project,
        "box",
        name="Box A",
        params={"length": 10, "width": 10, "height": 10},
    )
    add_part(
        project,
        "cylinder",
        name="Box-A",
        position=[20, 0, 0],
        params={"radius": 2, "height": 10},
    )

    macro = generate_macro(project, str(tmp_path / "labels.stl"), export_format="stl")
    ast.parse(macro)

    assert "obj_Box_A = doc.addObject('Part::Box', 'Box_A')" in macro
    assert "obj_Box_A001 = doc.addObject('Part::Cylinder', 'Box_A001')" in macro
    assert "obj_Box_A.Placement.Base = FreeCAD.Vector(0.0, 0.0, 0.0)" in macro
    assert "obj_Box_A001.Placement.Base = FreeCAD.Vector(20.0, 0.0, 0.0)" in macro
    assert "obj_Box_A.Radius" not in macro
    assert "obj_Box_A001.Radius = 2" in macro or "obj_Box_A001.Radius = 2.0" in macro

    assert _visible_labels(macro) == ["Box_A", "Box_A001"]
    assert _export_candidates(macro) == ["obj_Box_A", "obj_Box_A001"]

    preview = _generate_preview_macro(
        project,
        outputs=[],
        width=64,
        height=64,
        background="White",
    )
    motion = _generate_motion_macro(
        project,
        frames=[],
        camera="hero",
        width=64,
        height=64,
        background="White",
        fit_mode="initial",
    )
    ast.parse(preview)
    ast.parse(motion)
    for script in (preview, motion):
        assert "obj_Box_A = doc.addObject('Part::Box', 'Box_A')" in script
        assert "obj_Box_A001 = doc.addObject('Part::Cylinder', 'Box_A001')" in script
        assert "obj_Box_A001.Placement.Base = FreeCAD.Vector(20.0, 0.0, 0.0)" in script
    assert "'1': obj_Box_A," in motion
    assert "'2': obj_Box_A001," in motion


def test_boolean_operands_with_colliding_names_stay_distinct(tmp_path):
    """A cut of Box A and Box-A must reference both solids and export the result."""
    project = create_document()
    add_part(project, "box", name="Box A", params={"length": 10, "width": 10, "height": 10})
    add_part(
        project,
        "cylinder",
        name="Box-A",
        position=[0, 0, 0],
        params={"radius": 2, "height": 10},
    )
    boolean_op(project, "cut", 0, 1, name="Cut")

    macro = generate_macro(project, str(tmp_path / "cut.step"))
    ast.parse(macro)

    assert "obj_Cut.Base = obj_Box_A" in macro
    assert "obj_Cut.Tool = obj_Box_A001" in macro
    assert "doc.addObject('Part::Cut', 'Cut')" in macro
    assert _export_candidates(macro) == ["obj_Cut"]
    assert _visible_labels(macro) == ["Cut"]


def test_construction_circle_is_not_part_of_the_pad_profile(tmp_path):
    """construction=True must reach addGeometry so a pad does not cut that circle."""
    project = create_document()
    create_sketch(project, name="Sketch")
    add_rectangle(project, 0, corner=[0, 0], width=20, height=20)
    circle = add_circle(project, 0, center=[10, 10], radius=2)
    set_construction(project, 0, circle["id"], flag=True)
    create_body(project, name="Body")
    pad(project, 0, 0, length=10)

    macro = generate_macro(project, str(tmp_path / "construction.stl"), export_format="stl")
    ast.parse(macro)

    circle_calls = re.findall(
        r"addGeometry\(Part\.Circle\((?:.|\n)*?\), (True|False)\)",
        macro,
    )
    assert circle_calls == ["True"]

    line_calls = re.findall(
        r"addGeometry\(Part\.LineSegment\((?:.|\n)*?\), (True|False)\)",
        macro,
    )
    assert line_calls
    assert set(line_calls) == {"False"}
    assert "feat_Body_" in macro and ".Profile = sketch_Sketch" in macro
    assert _export_candidates(macro) == ["body_Body"]


def test_construction_rectangle_element_marks_every_edge(tmp_path):
    """A rectangle element flagged construction passes True for each edge."""
    project = create_document()
    project["sketches"] = [
        {
            "name": "Sketch",
            "plane": "XY",
            "offset": 0.0,
            "elements": [
                {
                    "type": "rectangle",
                    "corner": [0, 0],
                    "width": 20,
                    "height": 20,
                    "construction": True,
                }
            ],
        }
    ]

    macro = generate_macro(project, str(tmp_path / "rect.step"))
    ast.parse(macro)
    flags = []
    for line in macro.splitlines():
        if "addGeometry(Part.LineSegment" not in line:
            continue
        flags.append("True" if line.rstrip().endswith(", True)") else "False")
    assert flags == ["True", "True", "True", "True"]


def test_colliding_sketch_names_keep_the_padded_profile(tmp_path):
    """The pad profile follows the suffixed sketch, not the first namesake."""
    project = create_document()
    create_sketch(project, name="Sketch A")
    create_sketch(project, name="Sketch-A")
    add_rectangle(project, 1, corner=[0, 0], width=5, height=5)
    create_body(project, name="Body")
    pad(project, 0, 1, length=4)

    macro = generate_macro(project, str(tmp_path / "sketches.step"))
    ast.parse(macro)
    assert "doc.addObject('Sketcher::SketchObject', 'Sketch_A')" in macro
    assert "doc.addObject('Sketcher::SketchObject', 'Sketch_A001')" in macro
    assert ".Profile = sketch_Sketch_A001" in macro
    assert ".Profile = sketch_Sketch_A\n" not in macro


def test_body_origin_objects_do_not_steal_later_labels(tmp_path):
    """PartDesign origin objects occupy Origin/X_Axis/etc. before later features."""
    project = create_document()
    create_body(project, name="Body")
    feature = additive_box(project, 0, length=4, width=4, height=4)
    feature["name"] = "X_Axis"
    create_body(project, name="Origin")

    macro = generate_macro(project, str(tmp_path / "origin.step"))
    ast.parse(macro)
    assert "doc.addObject('PartDesign::Body', 'Body')" in macro
    assert "doc.addObject('PartDesign::Body', 'Origin001')" in macro
    assert "newObject('PartDesign::AdditiveBox', 'X_Axis001')" in macro
    assert _visible_labels(macro) == ["Body", "Origin001"]
    assert _export_candidates(macro) == ["body_Body", "body_Origin001"]
