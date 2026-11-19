"""Real archive and geometry checks for the CLI's millimeter contract."""

from dataclasses import replace
import json
import zipfile
from xml.etree import ElementTree as ET

from click.testing import CliRunner
import numpy as np
import pytest
import trimesh

from cli_anything.threemf.core import parser
from cli_anything.threemf.threemf_cli import cli
from cli_anything.threemf.utils import threemf_backend as backend


UNITS = [
    ("micron", 0.001),
    ("millimeter", 1.0),
    ("centimeter", 10.0),
    ("inch", 25.4),
    ("foot", 304.8),
    ("meter", 1000.0),
]
NS = parser.NS_CORE


def _tag(name):
    return f"{{{NS}}}{name}"


def _archive(path, unit, meshes, assembly=False):
    """Write model-space coordinates independently of the production writer."""
    attrs = {} if unit is None else {"unit": unit}
    root = ET.Element(_tag("model"), attrs)
    resources = ET.SubElement(root, _tag("resources"))
    for index, mesh in enumerate(meshes, 1):
        obj = ET.SubElement(resources, _tag("object"), id=str(index), type="model")
        mesh_el = ET.SubElement(obj, _tag("mesh"))
        vertices = ET.SubElement(mesh_el, _tag("vertices"))
        for point in mesh.vertices:
            ET.SubElement(vertices, _tag("vertex"), {
                axis: repr(float(value)) for axis, value in zip("xyz", point)
            })
        triangles = ET.SubElement(mesh_el, _tag("triangles"))
        for face in mesh.faces:
            ET.SubElement(triangles, _tag("triangle"), {
                f"v{index}": str(int(value))
                for index, value in enumerate(face, 1)
            })
    build = ET.SubElement(root, _tag("build"))
    if assembly:
        obj = ET.SubElement(resources, _tag("object"), id="3", type="model")
        components = ET.SubElement(obj, _tag("components"))
        ET.SubElement(components, _tag("component"), objectid="1",
                      transform="1 0 0 0 1 0 0 0 1 2 0 0")
        ET.SubElement(components, _tag("component"), objectid="2",
                      transform="0 1 0 -1 0 0 0 0 1 0 3 0")
        ET.SubElement(build, _tag("item"), objectid="3",
                      transform="1 0 0 0 1 0 0 0 1 0 0 4")
    else:
        for index in range(1, len(meshes) + 1):
            ET.SubElement(build, _tag("item"), objectid=str(index))
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("3D/3dmodel.model", ET.tostring(root))
        archive.writestr("_rels/.rels", (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="model" Target="/3D/3dmodel.model" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
            '</Relationships>'
        ))
        archive.writestr("[Content_Types].xml", (
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
            '</Types>'
        ))
        archive.writestr("Metadata/settings.txt", b"slicer settings\n")


def _model(path):
    with zipfile.ZipFile(path) as archive:
        return ET.fromstring(archive.read("3D/3dmodel.model"))


def _vertices(root, object_id="1"):
    obj = root.find(f"{_tag('resources')}/{_tag('object')}[@id='{object_id}']")
    return np.array([
        [float(vertex.get(axis)) for axis in "xyz"]
        for vertex in obj.findall(f"{_tag('mesh')}/{_tag('vertices')}/{_tag('vertex')}")
    ])


@pytest.mark.parametrize("unit,scale", UNITS)
def test_model_units_are_converted_before_geometry_analysis(tmp_path, unit, scale):
    source = tmp_path / "cube.3mf"
    cube = trimesh.creation.box(extents=(1, 1, 1))
    _archive(source, unit, [cube])
    data = parser.parse_3mf(str(source))

    assert data.unit == unit
    np.testing.assert_allclose(data.meshes[0].vertices, cube.vertices * scale)
    stats = backend.compute_mesh_stats(data.meshes[0])
    assert stats["bounding_box"]["size"] == pytest.approx([scale] * 3)
    assert stats["volume_mm3"] == pytest.approx(scale ** 3)
    assert stats["surface_area_mm2"] == pytest.approx(6 * scale ** 2)


@pytest.mark.parametrize("unit,scale", UNITS)
def test_programmatic_millimeter_meshes_are_written_in_declared_units(tmp_path, unit, scale):
    cube = trimesh.creation.box(extents=(scale, scale, scale))
    mesh = parser.MeshData("1", "cube", np.array(cube.vertices), np.array(cube.faces))
    data = parser.ThreeMFData((mesh,), unit, "3D/3dmodel.model", {}, {}, "")
    output = tmp_path / "written.3mf"
    parser.write_3mf(data, str(output))

    root = _model(output)
    assert root.get("unit") == unit
    np.testing.assert_allclose(_vertices(root), cube.vertices / scale)
    np.testing.assert_allclose(parser.parse_3mf(str(output)).meshes[0].vertices,
                               mesh.vertices)


def test_missing_unit_keeps_millimeter_default(tmp_path):
    source = tmp_path / "default.3mf"
    cube = trimesh.creation.box(extents=(2, 3, 4))
    _archive(source, None, [cube])
    data = parser.parse_3mf(str(source))
    assert data.unit == "millimeter"
    np.testing.assert_array_equal(data.meshes[0].vertices, cube.vertices)


def test_unit_conversion_preserves_other_objects_and_assembly_transforms(tmp_path):
    source = tmp_path / "assembly.3mf"
    output = tmp_path / "edited.3mf"
    cube = trimesh.creation.box(extents=(1, 1, 1))
    _archive(source, "inch", [cube, cube], assembly=True)
    data = parser.parse_3mf(str(source))
    moved = replace(data.meshes[0], vertices=data.meshes[0].vertices + [25.4, 0, 0])
    parser.write_3mf(replace(data, meshes=(moved, data.meshes[1])), str(output))

    original, written = _model(source), _model(output)
    assert written.get("unit") == "inch"
    np.testing.assert_allclose(_vertices(written), cube.vertices + [1, 0, 0])
    np.testing.assert_allclose(_vertices(written, "2"), cube.vertices)
    for tag in ("components", "build"):
        assert ET.tostring(written.find(f".//{_tag(tag)}")) == ET.tostring(
            original.find(f".//{_tag(tag)}")
        )
    with zipfile.ZipFile(source) as before, zipfile.ZipFile(output) as after:
        for name in ("_rels/.rels", "[Content_Types].xml", "Metadata/settings.txt"):
            assert before.read(name) == after.read(name)


def test_public_info_reports_physical_millimeter_dimensions(tmp_path):
    source = tmp_path / "inch-cube.3mf"
    _archive(source, "inch", [trimesh.creation.box(extents=(1, 1, 1))])
    runner = CliRunner()
    result = runner.invoke(cli, ["--json", "info", str(source)])
    assert result.exit_code == 0, result.output
    info = json.loads(result.output)
    assert info["unit"] == "inch"
    assert info["objects"][0]["bounding_box"]["size"] == pytest.approx([25.4] * 3)
    assert info["objects"][0]["volume_mm3"] == pytest.approx(25.4 ** 3)


@pytest.mark.parametrize("unit,scale", [("inch", 25.4), ("meter", 1000.0)])
def test_public_inspect_resize_round_trip_uses_millimeters(tmp_path, unit, scale):
    source = tmp_path / "washer.3mf"
    output = tmp_path / "resized.3mf"
    washer = trimesh.creation.annulus(r_min=4, r_max=20, height=25.4, sections=64)
    washer.apply_scale(1 / scale)
    _archive(source, unit, [washer])
    runner = CliRunner()

    inspected = runner.invoke(cli, ["--json", "inspect", str(source), "--axis", "2"])
    assert inspected.exit_code == 0, inspected.output
    holes = json.loads(inspected.output)
    assert holes["hole_count"] == 1
    assert holes["holes"][0]["diameter"] == pytest.approx(8.0, abs=0.04)

    resized = runner.invoke(cli, [
        "--json", "resize", str(source), "--axis", "2", "--hole", "0",
        "--diameter", "10", "--output", str(output),
    ])
    assert resized.exit_code == 0, resized.output
    assert json.loads(resized.output)["changes"][0]["vertices_moved"] > 0
    assert _model(output).get("unit") == unit
    physical_vertices = _vertices(_model(output)) * scale
    radii = np.linalg.norm(physical_vertices[:, :2], axis=1)
    assert np.min(radii) == pytest.approx(5.0, abs=0.02)
    assert np.max(radii) == pytest.approx(20.0, abs=0.001)
    assert np.ptp(physical_vertices[:, 2]) == pytest.approx(25.4)

    reinspected = runner.invoke(cli, ["--json", "inspect", str(output), "--axis", "2"])
    assert reinspected.exit_code == 0, reinspected.output
    assert json.loads(reinspected.output)["holes"][0]["diameter"] == pytest.approx(10.0, abs=0.04)


def test_unsupported_units_fail_without_silently_assuming_millimeters(tmp_path):
    source = tmp_path / "unknown.3mf"
    _archive(source, "yard", [trimesh.creation.box()])
    result = CliRunner().invoke(cli, ["--json", "info", str(source)])
    assert result.exit_code != 0
    assert "unit" in json.loads(result.output)["error"].lower()
