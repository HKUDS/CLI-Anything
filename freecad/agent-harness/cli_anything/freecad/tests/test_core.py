"""
Comprehensive unit tests for the cli-anything-freecad core modules.

All tests use synthetic data and require no external dependencies
beyond pytest.
"""

import json
import math
import os

import pytest

from cli_anything.freecad.core.document import (
    PROFILES,
    create_document,
    get_document_info,
    list_profiles,
    open_document,
    save_document,
)
from cli_anything.freecad.core.parts import (
    PRIMITIVES,
    add_part,
    boolean_op,
    get_part,
    list_parts,
    remove_part,
    transform_part,
)
from cli_anything.freecad.core.sketch import (
    add_arc,
    add_circle,
    add_constraint,
    add_line,
    add_rectangle,
    close_sketch,
    create_sketch,
    get_sketch,
    list_sketches,
)
from cli_anything.freecad.core.body import (
    chamfer,
    create_body,
    datum_plane,
    datum_line,
    datum_point,
    fillet,
    get_body,
    hole_feature,
    list_bodies,
    local_coordinate_system,
    pad,
    pocket,
    revolution,
    toggle_freeze,
)
from cli_anything.freecad.core.materials import (
    PRESETS,
    assign_material,
    create_material,
    get_material,
    list_materials,
    list_presets,
    set_material_property,
)
from cli_anything.freecad.core.session import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(**overrides):
    """Create a minimal valid project dict, applying any overrides."""
    proj = create_document(name="TestProject")
    proj.update(overrides)
    return proj


# ===========================================================================
# TestDocument
# ===========================================================================


class TestDocument:
    """Tests for the document module."""

    def test_create_default(self):
        proj = create_document()
        assert proj["name"] == "Untitled"
        assert proj["units"] == "mm"
        assert proj["version"] == "1.0"
        assert proj["parts"] == []
        assert proj["sketches"] == []
        assert proj["bodies"] == []
        assert proj["materials"] == []
        assert "created" in proj["metadata"]
        assert "modified" in proj["metadata"]
        assert "software" in proj["metadata"]

    def test_create_with_profile(self):
        proj = create_document(name="ImperialProject", profile="imperial")
        assert proj["units"] == "in"
        assert proj["name"] == "ImperialProject"

        proj2 = create_document(profile="metric_large")
        assert proj2["units"] == "m"

    def test_create_invalid_profile(self):
        with pytest.raises(ValueError, match="Unknown profile"):
            create_document(profile="nonexistent_profile")

    def test_save_and_open(self, tmp_path):
        proj = create_document(name="RoundTrip", units="mm")
        add_part(proj, "box", name="TestBox")

        filepath = str(tmp_path / "roundtrip.json")
        abs_path = save_document(proj, filepath)
        assert os.path.isfile(abs_path)

        loaded = open_document(filepath)
        assert loaded["name"] == "RoundTrip"
        assert loaded["units"] == "mm"
        assert len(loaded["parts"]) == 1
        assert loaded["parts"][0]["name"] == "TestBox"

    def test_open_nonexistent(self, tmp_path):
        missing = str(tmp_path / "does_not_exist.json")
        with pytest.raises(FileNotFoundError):
            open_document(missing)

    def test_get_info(self):
        proj = create_document(name="InfoTest")
        info = get_document_info(proj)
        assert info["name"] == "InfoTest"
        assert info["units"] == "mm"
        assert info["parts_count"] == 0
        assert info["sketches_count"] == 0
        assert info["bodies_count"] == 0
        assert info["materials_count"] == 0

    def test_get_info_with_data(self):
        proj = create_document(name="DataTest")
        add_part(proj, "box")
        add_part(proj, "cylinder")
        create_sketch(proj)

        info = get_document_info(proj)
        assert info["parts_count"] == 2
        assert info["sketches_count"] == 1

    def test_list_profiles(self):
        profiles = list_profiles()
        assert isinstance(profiles, list)
        assert len(profiles) == len(PROFILES)
        names = {p["name"] for p in profiles}
        assert "default" in names
        assert "imperial" in names
        for p in profiles:
            assert "name" in p
            assert "units" in p
            assert "description" in p


# ===========================================================================
# TestParts
# ===========================================================================


class TestParts:
    """Tests for the parts module."""

    def test_add_box_defaults(self):
        proj = _make_project()
        part = add_part(proj, "box")
        assert part["type"] == "box"
        assert part["name"] == "Box"
        assert part["params"]["length"] == 10.0
        assert part["params"]["width"] == 10.0
        assert part["params"]["height"] == 10.0
        assert part["placement"]["position"] == [0.0, 0.0, 0.0]
        assert part["placement"]["rotation"] == [0.0, 0.0, 0.0]
        assert part["visible"] is True
        assert part["material_index"] is None
        assert len(proj["parts"]) == 1

    @pytest.mark.parametrize("ptype", ["box", "cylinder", "sphere", "cone", "torus", "wedge"])
    def test_add_all_primitives(self, ptype):
        proj = _make_project()
        part = add_part(proj, ptype)
        assert part["type"] == ptype
        # All default params from PRIMITIVES should be present
        for key in PRIMITIVES[ptype]:
            assert key in part["params"]
            assert part["params"][key] == PRIMITIVES[ptype][key]

    def test_add_with_position_rotation(self):
        proj = _make_project()
        part = add_part(proj, "box", position=[1.0, 2.0, 3.0], rotation=[45.0, 0.0, 90.0])
        assert part["placement"]["position"] == [1.0, 2.0, 3.0]
        assert part["placement"]["rotation"] == [45.0, 0.0, 90.0]

    def test_add_with_custom_params(self):
        proj = _make_project()
        part = add_part(proj, "box", params={"length": 20.0, "width": 5.0})
        assert part["params"]["length"] == 20.0
        assert part["params"]["width"] == 5.0
        assert part["params"]["height"] == 10.0  # default unchanged

    def test_add_invalid_type(self):
        proj = _make_project()
        with pytest.raises(ValueError, match="Unknown part_type"):
            add_part(proj, "hexagon")

    def test_remove_part(self):
        proj = _make_project()
        add_part(proj, "box", name="A")
        add_part(proj, "cylinder", name="B")
        assert len(proj["parts"]) == 2

        removed = remove_part(proj, 0)
        assert removed["name"] == "A"
        assert len(proj["parts"]) == 1
        assert proj["parts"][0]["name"] == "B"

    def test_remove_invalid_index(self):
        proj = _make_project()
        add_part(proj, "box")
        with pytest.raises(IndexError):
            remove_part(proj, 5)
        with pytest.raises(IndexError):
            remove_part(proj, -1)

    def test_list_parts(self):
        proj = _make_project()
        assert list_parts(proj) == []
        add_part(proj, "box", name="A")
        add_part(proj, "sphere", name="B")
        parts = list_parts(proj)
        assert len(parts) == 2
        assert parts[0]["name"] == "A"
        assert parts[1]["name"] == "B"

    def test_transform_part(self):
        proj = _make_project()
        add_part(proj, "box")
        updated = transform_part(proj, 0, position=[10.0, 20.0, 30.0])
        assert updated["placement"]["position"] == [10.0, 20.0, 30.0]
        # Rotation unchanged
        assert updated["placement"]["rotation"] == [0.0, 0.0, 0.0]

        updated2 = transform_part(proj, 0, rotation=[90.0, 0.0, 0.0])
        assert updated2["placement"]["rotation"] == [90.0, 0.0, 0.0]
        # Position unchanged from previous transform
        assert updated2["placement"]["position"] == [10.0, 20.0, 30.0]

    def test_boolean_cut(self):
        proj = _make_project()
        add_part(proj, "box", name="Base")
        add_part(proj, "cylinder", name="Tool")
        result = boolean_op(proj, "cut", 0, 1)

        assert result["type"] == "cut"
        assert result["params"]["base_id"] == proj["parts"][0]["id"]
        assert result["params"]["tool_id"] == proj["parts"][1]["id"]
        assert result["visible"] is True
        # Operands should be hidden
        assert proj["parts"][0]["visible"] is False
        assert proj["parts"][1]["visible"] is False
        assert len(proj["parts"]) == 3

    def test_boolean_fuse_common(self):
        proj = _make_project()
        add_part(proj, "box", name="A")
        add_part(proj, "box", name="B")

        fuse_result = boolean_op(proj, "fuse", 0, 1)
        assert fuse_result["type"] == "fuse"

        # Add two more for common test
        add_part(proj, "sphere", name="C")
        add_part(proj, "sphere", name="D")
        common_result = boolean_op(proj, "common", 3, 4)
        assert common_result["type"] == "common"

        with pytest.raises(ValueError, match="Unknown boolean op"):
            boolean_op(proj, "intersect", 0, 1)

        with pytest.raises(ValueError, match="must differ"):
            boolean_op(proj, "cut", 0, 0)


# ===========================================================================
# TestSketch
# ===========================================================================


class TestSketch:
    """Tests for the sketch module."""

    def test_create_sketch(self):
        proj = _make_project()
        sk = create_sketch(proj, name="MySketch", plane="XZ", offset=5.0)
        assert sk["name"] == "MySketch"
        assert sk["plane"] == "XZ"
        assert sk["offset"] == 5.0
        assert sk["elements"] == []
        assert sk["constraints"] == []
        assert sk["closed"] is False
        assert len(proj["sketches"]) == 1

        # Invalid plane
        with pytest.raises(ValueError, match="Invalid plane"):
            create_sketch(proj, plane="AB")

    def test_add_line(self):
        proj = _make_project()
        create_sketch(proj)
        line = add_line(proj, 0, start=[0.0, 0.0], end=[10.0, 5.0])
        assert line["type"] == "line"
        assert line["start"] == [0.0, 0.0]
        assert line["end"] == [10.0, 5.0]
        assert len(proj["sketches"][0]["elements"]) == 1

    def test_add_circle(self):
        proj = _make_project()
        create_sketch(proj)
        circle = add_circle(proj, 0, center=[1.0, 2.0], radius=8.0)
        assert circle["type"] == "circle"
        assert circle["center"] == [1.0, 2.0]
        assert circle["radius"] == 8.0

        with pytest.raises(ValueError, match="positive"):
            add_circle(proj, 0, radius=-1.0)

    def test_add_rectangle(self):
        proj = _make_project()
        create_sketch(proj)
        result = add_rectangle(proj, 0, corner=[0.0, 0.0], width=20.0, height=10.0)

        assert result["type"] == "rectangle"
        assert len(result["line_ids"]) == 4
        assert len(result["constraint_ids"]) == 4
        assert result["width"] == 20.0
        assert result["height"] == 10.0

        # 4 line elements and 4 constraints should be in the sketch
        sk = proj["sketches"][0]
        assert len(sk["elements"]) == 4
        assert len(sk["constraints"]) == 4

    def test_add_arc(self):
        proj = _make_project()
        create_sketch(proj)
        arc = add_arc(proj, 0, center=[0.0, 0.0], radius=10.0, start_angle=0.0, end_angle=90.0)
        assert arc["type"] == "arc"
        assert arc["radius"] == 10.0
        assert arc["start_angle"] == 0.0
        assert arc["end_angle"] == 90.0
        # Check computed start/end points
        assert arc["start_point"][0] == pytest.approx(10.0)
        assert arc["start_point"][1] == pytest.approx(0.0)
        assert arc["end_point"][0] == pytest.approx(0.0, abs=1e-10)
        assert arc["end_point"][1] == pytest.approx(10.0)

    def test_add_constraint_distance(self):
        proj = _make_project()
        create_sketch(proj)
        line = add_line(proj, 0, start=[0.0, 0.0], end=[10.0, 0.0])

        constraint = add_constraint(
            proj, 0, constraint_type="distance", elements=[line["id"]], value=15.0
        )
        assert constraint["type"] == "distance"
        assert constraint["value"] == 15.0
        assert constraint["elements"] == [line["id"]]

        # Missing value for dimensional constraint
        with pytest.raises(ValueError, match="requires a numeric value"):
            add_constraint(proj, 0, constraint_type="distance", elements=[line["id"]])

        # Unknown constraint type
        with pytest.raises(ValueError, match="Unknown constraint type"):
            add_constraint(proj, 0, constraint_type="magical", elements=[line["id"]])

    def test_close_sketch(self):
        proj = _make_project()
        create_sketch(proj)
        add_line(proj, 0)

        closed = close_sketch(proj, 0)
        assert closed["closed"] is True

        # Cannot add elements to a closed sketch
        with pytest.raises(ValueError, match="closed sketch"):
            add_line(proj, 0)

        # Cannot close an already closed sketch
        with pytest.raises(ValueError, match="already closed"):
            close_sketch(proj, 0)

    def test_list_and_get_sketch(self):
        proj = _make_project()
        create_sketch(proj, name="S1", plane="XY")
        create_sketch(proj, name="S2", plane="YZ")
        add_line(proj, 0)

        summaries = list_sketches(proj)
        assert len(summaries) == 2
        assert summaries[0]["name"] == "S1"
        assert summaries[0]["plane"] == "XY"
        assert summaries[0]["element_count"] == 1
        assert summaries[1]["name"] == "S2"
        assert summaries[1]["plane"] == "YZ"

        sk = get_sketch(proj, 1)
        assert sk["name"] == "S2"

        with pytest.raises(IndexError):
            get_sketch(proj, 99)


# ===========================================================================
# TestBody
# ===========================================================================


class TestBody:
    """Tests for the body module."""

    def _project_with_sketch(self):
        """Return a project with one closed sketch containing a rectangle."""
        proj = _make_project()
        create_sketch(proj, name="BaseSketch")
        add_rectangle(proj, 0, corner=[0, 0], width=10, height=10)
        close_sketch(proj, 0)
        return proj

    def test_create_body(self):
        proj = _make_project()
        body = create_body(proj, name="MyBody")
        assert body["name"] == "MyBody"
        assert body["features"] == []
        assert body["base_sketch_index"] is None
        assert len(proj["bodies"]) == 1

        # Auto-naming
        body2 = create_body(proj)
        assert body2["name"] == "Body"  # first auto "Body" is taken by none; unique check

    def test_pad(self):
        proj = self._project_with_sketch()
        create_body(proj, name="PadBody")
        feature = pad(proj, body_index=0, sketch_index=0, length=15.0, symmetric=True)
        assert feature["type"] == "pad"
        assert feature["length"] == 15.0
        assert feature["symmetric"] is True
        assert feature["reversed"] is False
        assert proj["bodies"][0]["base_sketch_index"] == 0

        with pytest.raises(ValueError, match="positive"):
            pad(proj, body_index=0, sketch_index=0, length=-5.0)

    def test_pocket(self):
        proj = self._project_with_sketch()
        create_body(proj, name="PocketBody")
        # Add a pad first so body has features
        pad(proj, body_index=0, sketch_index=0, length=20.0)

        # Create a second sketch for the pocket
        create_sketch(proj, name="PocketSketch")
        add_rectangle(proj, 1, corner=[2, 2], width=3, height=3)
        close_sketch(proj, 1)

        feature = pocket(proj, body_index=0, sketch_index=1, length=5.0)
        assert feature["type"] == "pocket"
        assert feature["length"] == 5.0

    def test_fillet(self):
        proj = self._project_with_sketch()
        create_body(proj)
        pad(proj, body_index=0, sketch_index=0, length=10.0)

        feat = fillet(proj, body_index=0, radius=2.0, edges="all")
        assert feat["type"] == "fillet"
        assert feat["radius"] == 2.0
        assert feat["edges"] == "all"

        feat2 = fillet(proj, body_index=0, radius=1.0, edges=[0, 1, 2])
        assert feat2["edges"] == [0, 1, 2]

        with pytest.raises(ValueError, match="positive"):
            fillet(proj, body_index=0, radius=-1.0)

    def test_chamfer(self):
        proj = self._project_with_sketch()
        create_body(proj)
        pad(proj, body_index=0, sketch_index=0, length=10.0)

        feat = chamfer(proj, body_index=0, size=1.5, edges="all")
        assert feat["type"] == "chamfer"
        assert feat["size"] == 1.5
        assert feat["edges"] == "all"

        with pytest.raises(ValueError, match="positive"):
            chamfer(proj, body_index=0, size=0.0)

    def test_revolution(self):
        proj = self._project_with_sketch()
        create_body(proj)
        feat = revolution(proj, body_index=0, sketch_index=0, angle=180.0, axis="Y")
        assert feat["type"] == "revolution"
        assert feat["angle"] == 180.0
        assert feat["axis"] == "Y"
        assert feat["reversed"] is False

        with pytest.raises(ValueError, match="angle must be in"):
            revolution(proj, body_index=0, sketch_index=0, angle=0.0)

        with pytest.raises(ValueError, match="Invalid revolution axis"):
            revolution(proj, body_index=0, sketch_index=0, axis="W")

    def test_list_and_get_body(self):
        proj = self._project_with_sketch()
        create_body(proj, name="B1")
        create_body(proj, name="B2")
        pad(proj, body_index=0, sketch_index=0, length=10.0)

        summaries = list_bodies(proj)
        assert len(summaries) == 2
        assert summaries[0]["name"] == "B1"
        assert summaries[0]["feature_count"] == 1
        assert summaries[1]["name"] == "B2"
        assert summaries[1]["feature_count"] == 0

        body = get_body(proj, 0)
        assert body["name"] == "B1"

        with pytest.raises(IndexError):
            get_body(proj, 99)


# ===========================================================================
# TestMaterials
# ===========================================================================


class TestMaterials:
    """Tests for the materials module."""

    def test_create_default(self):
        proj = _make_project()
        mat = create_material(proj)
        assert mat["name"] == "Material"
        assert mat["preset"] is None
        assert mat["color"] == [0.8, 0.8, 0.8, 1.0]
        assert mat["metallic"] == 0.0
        assert mat["roughness"] == 0.5
        assert mat["assigned_to"] == []
        assert len(proj["materials"]) == 1

    def test_create_from_preset(self):
        proj = _make_project()
        mat = create_material(proj, preset="steel")
        assert mat["preset"] == "steel"
        assert mat["color"] == PRESETS["steel"]["color"]
        assert mat["metallic"] == PRESETS["steel"]["metallic"]
        assert mat["roughness"] == PRESETS["steel"]["roughness"]
        # Name is derived from preset key
        assert mat["name"] == "Steel"

        with pytest.raises(ValueError, match="Unknown preset"):
            create_material(proj, preset="unobtanium")

    def test_create_with_color(self):
        proj = _make_project()
        mat = create_material(proj, name="Red", color=[1.0, 0.0, 0.0])
        # 3-component color gets alpha appended
        assert mat["color"] == [1.0, 0.0, 0.0, 1.0]

        mat2 = create_material(proj, name="SemiRed", color=[1.0, 0.0, 0.0, 0.5])
        assert mat2["color"] == [1.0, 0.0, 0.0, 0.5]

    def test_assign_to_part(self):
        proj = _make_project()
        add_part(proj, "box", name="MyBox")
        create_material(proj, name="BlueMat", color=[0.0, 0.0, 1.0])

        result = assign_material(proj, material_index=0, part_index=0)
        assert result["material"] == "BlueMat"
        assert result["part"] == "MyBox"
        # Material should track the assignment
        assert 0 in proj["materials"][0]["assigned_to"]
        # Part should reference the material
        assert proj["parts"][0]["material_index"] == 0

    def test_set_property(self):
        proj = _make_project()
        create_material(proj, name="Editable")

        set_material_property(proj, 0, "roughness", 0.9)
        assert proj["materials"][0]["roughness"] == 0.9

        set_material_property(proj, 0, "name", "Renamed")
        assert proj["materials"][0]["name"] == "Renamed"

        set_material_property(proj, 0, "color", [0.1, 0.2, 0.3, 1.0])
        assert proj["materials"][0]["color"] == [0.1, 0.2, 0.3, 1.0]

    def test_set_invalid_property(self):
        proj = _make_project()
        create_material(proj)

        with pytest.raises(ValueError):
            set_material_property(proj, 0, "nonexistent_prop", 42)

        with pytest.raises(ValueError, match="maximum"):
            set_material_property(proj, 0, "metallic", 2.0)

    def test_list_presets(self):
        presets = list_presets()
        assert isinstance(presets, list)
        assert len(presets) == len(PRESETS)
        names = {p["name"] for p in presets}
        assert "steel" in names
        assert "gold" in names
        for p in presets:
            assert "name" in p
            assert "color" in p
            assert "metallic" in p
            assert "roughness" in p


# ===========================================================================
# TestSession
# ===========================================================================


class TestSession:
    """Tests for the session module."""

    def test_status_no_project(self):
        session = Session()
        status = session.status()
        assert status["has_project"] is False
        assert status["project_path"] is None
        assert status["modified"] is False
        assert status["undo_depth"] == 0
        assert status["redo_depth"] == 0

        with pytest.raises(RuntimeError, match="No project"):
            session.get_project()

    def test_set_project(self):
        session = Session()
        proj = create_document(name="SessionTest")
        session.set_project(proj, path="/tmp/test.json")

        assert session.get_project()["name"] == "SessionTest"
        assert session.project_path == "/tmp/test.json"
        status = session.status()
        assert status["has_project"] is True
        assert status["modified"] is False

    def test_snapshot_and_undo(self):
        session = Session()
        proj = create_document(name="UndoTest")
        session.set_project(proj)

        # Take a snapshot, then mutate
        session.snapshot("before adding box")
        add_part(session.get_project(), "box", name="TempBox")
        assert len(session.get_project()["parts"]) == 1

        # Undo should restore the state before the mutation
        desc = session.undo()
        assert desc == "before adding box"
        assert len(session.get_project()["parts"]) == 0

        # Undo with empty stack returns None
        assert session.undo() is None

    def test_undo_redo_cycle(self):
        session = Session()
        proj = create_document(name="RedoTest")
        session.set_project(proj)

        # Snapshot -> mutate -> undo -> redo
        session.snapshot("add cylinder")
        add_part(session.get_project(), "cylinder", name="Cyl")
        assert len(session.get_project()["parts"]) == 1

        session.undo()
        assert len(session.get_project()["parts"]) == 0
        assert session.status()["redo_depth"] == 1

        desc = session.redo()
        assert desc == "add cylinder"
        assert len(session.get_project()["parts"]) == 1

        # Redo with empty stack returns None
        assert session.redo() is None

    def test_save_session(self, tmp_path):
        session = Session()
        proj = create_document(name="SaveTest")
        session.set_project(proj)

        filepath = str(tmp_path / "session_save.json")
        saved_path = session.save_session(path=filepath)
        assert os.path.isfile(saved_path)
        assert session.status()["modified"] is False

        # Verify the file contains valid JSON matching the project
        with open(saved_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["name"] == "SaveTest"

        # Save without path after initial save should use stored path
        session.snapshot("mark modified")
        saved_again = session.save_session()
        assert saved_again == saved_path

    def test_list_history(self):
        session = Session()
        proj = create_document(name="HistoryTest")
        session.set_project(proj)

        session.snapshot("step 1")
        add_part(session.get_project(), "box")
        session.snapshot("step 2")
        add_part(session.get_project(), "cylinder")
        session.snapshot("step 3")

        history = session.list_history()
        assert len(history) == 3
        # Newest first
        assert history[0]["description"] == "step 3"
        assert history[1]["description"] == "step 2"
        assert history[2]["description"] == "step 1"
        # Each entry has required keys
        for entry in history:
            assert "index" in entry
            assert "timestamp" in entry
            assert "description" in entry


# ===========================================================================
# TestFreeCAD11Features — New features added for FreeCAD 1.1
# ===========================================================================


class TestFreeCAD11Features:
    """Tests for FreeCAD 1.1 new features across modules."""

    # -- Body: LocalCoordinateSystem --

    def test_local_coordinate_system_default(self):
        proj = _make_project()
        body = create_body(proj, name="LCSBody")
        feat = local_coordinate_system(proj, 0)
        assert feat["type"] == "local_coordinate_system"
        assert feat["position"] == [0.0, 0.0, 0.0]
        assert feat["x_axis"] == [1.0, 0.0, 0.0]
        assert feat["y_axis"] == [0.0, 1.0, 0.0]
        assert feat["z_axis"] == [0.0, 0.0, 1.0]

    def test_local_coordinate_system_custom_axes(self):
        proj = _make_project()
        create_body(proj, name="LCSBody2")
        feat = local_coordinate_system(
            proj, 0,
            position=[10.0, 20.0, 30.0],
            x_axis=[0.0, 1.0, 0.0],
            z_axis=[1.0, 0.0, 0.0],
        )
        assert feat["position"] == [10.0, 20.0, 30.0]
        assert feat["x_axis"] == [0.0, 1.0, 0.0]

    def test_local_coordinate_system_invalid_body(self):
        proj = _make_project()
        with pytest.raises(IndexError):
            local_coordinate_system(proj, 99)

    # -- Body: Datum attachment --

    def test_datum_plane_with_attachment(self):
        proj = _make_project()
        create_body(proj, name="DatumBody")
        feat = datum_plane(proj, 0, attachment_mode="flat_face",
                           attachment_refs=["Body.Face1"])
        assert feat["attachment_mode"] == "flat_face"
        assert feat["attachment_refs"] == ["Body.Face1"]

    def test_datum_line_with_attachment(self):
        proj = _make_project()
        create_body(proj, name="DatumBody2")
        feat = datum_line(proj, 0, attachment_mode="normal_to_edge",
                          attachment_refs=["Body.Edge1"])
        assert feat["attachment_mode"] == "normal_to_edge"

    def test_datum_point_with_attachment(self):
        proj = _make_project()
        create_body(proj, name="DatumBody3")
        feat = datum_point(proj, 0, attachment_mode="translate",
                           attachment_refs=["Body.Vertex1"])
        assert feat["attachment_mode"] == "translate"

    def test_datum_invalid_attachment_mode(self):
        proj = _make_project()
        create_body(proj, name="DatumBody4")
        with pytest.raises(ValueError, match="Invalid attachment_mode"):
            datum_plane(proj, 0, attachment_mode="nonexistent_mode")

    # -- Body: Hole Whitworth threads --

    def test_hole_whitworth_bsw(self):
        proj = _make_project()
        create_body(proj, name="HoleBody")
        sk = create_sketch(proj)
        add_line(proj, 0, [0, 0], [10, 0])
        close_sketch(proj, 0)
        pad(proj, 0, sketch_index=0, length=10.0)
        feat = hole_feature(proj, 0, sketch_index=0, diameter=6.0, depth=10.0,
                            threaded=True, thread_standard="BSW")
        assert feat["thread_standard"] == "BSW"

    def test_hole_npt_auto_taper(self):
        proj = _make_project()
        create_body(proj, name="HoleBody2")
        sk = create_sketch(proj)
        add_line(proj, 0, [0, 0], [10, 0])
        close_sketch(proj, 0)
        pad(proj, 0, sketch_index=0, length=10.0)
        feat = hole_feature(proj, 0, sketch_index=0, diameter=6.0, depth=10.0,
                            threaded=True, thread_standard="NPT", tapered=True)
        assert feat["tapered"] is True
        assert abs(feat["taper_angle"] - 1.7899) < 0.001

    def test_hole_invalid_thread_standard(self):
        proj = _make_project()
        create_body(proj, name="HoleBody3")
        sk = create_sketch(proj)
        add_line(proj, 0, [0, 0], [10, 0])
        close_sketch(proj, 0)
        pad(proj, 0, sketch_index=0, length=10.0)
        with pytest.raises(ValueError, match="Invalid thread_standard"):
            hole_feature(proj, 0, sketch_index=0, diameter=6.0, depth=10.0,
                         thread_standard="INVALID")

    # -- Body: Toggle freeze --

    def test_toggle_freeze(self):
        proj = _make_project()
        create_body(proj, name="FreezeBody")
        create_sketch(proj)
        add_line(proj, 0, [0, 0], [10, 0])
        close_sketch(proj, 0)
        pad(proj, 0, sketch_index=0, length=5.0)
        feat = toggle_freeze(proj, 0, 0)
        assert feat["frozen"] is True
        feat2 = toggle_freeze(proj, 0, 0)
        assert feat2["frozen"] is False

    def test_toggle_freeze_invalid_index(self):
        proj = _make_project()
        create_body(proj, name="FreezeBody2")
        with pytest.raises(IndexError):
            toggle_freeze(proj, 0, 99)
