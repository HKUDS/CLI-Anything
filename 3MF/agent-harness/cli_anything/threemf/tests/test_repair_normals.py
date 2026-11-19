"""Normal repair through the real geometry and public CLI pipelines."""

from dataclasses import replace
import json

from click.testing import CliRunner
import numpy as np
import pytest
import trimesh

from cli_anything.threemf.core import parser, repair
from cli_anything.threemf.threemf_cli import cli
from cli_anything.threemf.utils.threemf_backend import mesh_to_trimesh


def _mesh(tm):
    return parser.MeshData(
        object_id="1", name="part", vertices=np.array(tm.vertices),
        triangles=np.array(tm.faces),
    )


def _write(path, mesh):
    relationships = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="model" Target="/3D/3dmodel.model" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        '</Relationships>'
    )
    content_types = (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        '</Types>'
    )
    parser.write_3mf(parser.ThreeMFData(
        meshes=(mesh,), unit="millimeter", model_path="3D/3dmodel.model",
        metadata={}, raw_entries={
            "_rels/.rels": relationships.encode(),
            "[Content_Types].xml": content_types.encode(),
        }, source_path="",
    ), str(path))


def _properties_by_vertex(face, attrs):
    return {
        int(vertex): attrs.get(f"p{index}", attrs.get("p1"))
        for index, vertex in enumerate(face, 1)
    }


@pytest.mark.parametrize("all_faces", [False, True])
def test_repair_mesh_corrects_winding_and_outward_orientation(all_faces):
    tm = trimesh.creation.box(extents=(2, 3, 4))
    faces = np.array(tm.faces)
    if all_faces:
        faces = faces[:, ::-1]
    else:
        faces[0] = faces[0, ::-1]
    broken = replace(_mesh(tm), triangles=faces)
    original = broken.triangles.copy()

    fixed, report = repair.repair_mesh(broken)

    assert mesh_to_trimesh(fixed).is_winding_consistent
    assert mesh_to_trimesh(fixed).volume == pytest.approx(24.0)
    assert report["faces_reoriented"] == (len(faces) if all_faces else 1)
    np.testing.assert_array_equal(broken.triangles, original)


@pytest.mark.parametrize("attributes", [
    {"pid": "7", "p1": "0", "p2": "1", "p3": "2", "custom": "kept"},
    {"pid": "7", "p1": "0"},
    {"pid": "7", "p1": "0", "p3": "2"},
])
def test_fix_normals_keeps_properties_attached_to_vertices(attributes):
    tm = trimesh.creation.box()
    faces = np.array(tm.faces)[:, ::-1]
    original_attrs = tuple(dict(attributes) for _ in faces)
    mesh = replace(_mesh(tm), triangles=faces, triangle_attributes=original_attrs)

    fixed = repair.fix_normals(mesh)

    assert mesh_to_trimesh(fixed).volume == pytest.approx(1.0)
    for old_face, new_face, old_attrs, new_attrs in zip(
        mesh.triangles, fixed.triangles, original_attrs, fixed.triangle_attributes,
    ):
        assert _properties_by_vertex(old_face, old_attrs) == _properties_by_vertex(new_face, new_attrs)
        assert old_attrs["pid"] == new_attrs["pid"]
        assert old_attrs.get("custom") == new_attrs.get("custom")
    assert mesh.triangle_attributes == original_attrs


def test_repair_preserves_valid_hollow_geometry_and_reports_no_normal_changes():
    washer = _mesh(trimesh.creation.annulus(r_min=4, r_max=20, height=10, sections=64))
    fixed, report = repair.repair_mesh(washer)
    assert report["faces_reoriented"] == 0
    assert mesh_to_trimesh(fixed).volume == pytest.approx(mesh_to_trimesh(washer).volume)
    np.testing.assert_array_equal(fixed.triangles, washer.triangles)


def test_public_repair_corrects_normals_and_reports_them_in_json(tmp_path):
    source = tmp_path / "inverted.3mf"
    destination = tmp_path / "repaired.3mf"
    tm = trimesh.creation.box(extents=(2, 3, 4))
    _write(source, replace(_mesh(tm), triangles=np.array(tm.faces)[:, ::-1]))

    result = CliRunner().invoke(cli, [
        "--json", "repair", str(source), "--output", str(destination),
    ])

    assert result.exit_code == 0, result.output
    fixed = parser.parse_3mf(str(destination)).meshes[0]
    assert mesh_to_trimesh(fixed).volume == pytest.approx(24.0)
    assert json.loads(result.output)["repairs"]["faces_reoriented"] == 12


def test_public_repair_text_includes_normal_changes_in_total(tmp_path):
    source = tmp_path / "inverted.3mf"
    destination = tmp_path / "repaired.3mf"
    tm = trimesh.creation.box()
    _write(source, replace(_mesh(tm), triangles=np.array(tm.faces)[:, ::-1]))

    result = CliRunner().invoke(cli, ["repair", str(source), "--output", str(destination)])

    assert result.exit_code == 0, result.output
    assert "Faces reoriented:     12" in result.output
    assert "Total fixes:          12" in result.output


def test_resize_auto_repair_saves_changes_when_only_normals_need_repair(tmp_path):
    source = tmp_path / "washer.3mf"
    destination = tmp_path / "resized.3mf"
    tm = trimesh.creation.annulus(r_min=4, r_max=20, height=10, sections=64)
    faces = np.array(tm.faces)
    # Flip one outer-wall face; retain the inner wall used for hole detection.
    radii = np.linalg.norm(np.asarray(tm.triangles_center)[:, :2], axis=1)
    index = int(np.argmax(radii))
    faces[index] = faces[index, ::-1]
    _write(source, replace(_mesh(tm), triangles=faces))

    result = CliRunner().invoke(cli, [
        "--json", "resize", str(source), "--axis", "2", "--hole", "0",
        "--diameter", "10", "--output", str(destination),
    ])

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)["repairs"]
    assert report["faces_reoriented"] == 1
    assert report["vertices_merged"] == 0
    assert report["degenerate_faces_removed"] == 0
    assert report["unreferenced_vertices_removed"] == 0
    fixed = mesh_to_trimesh(parser.parse_3mf(str(destination)).meshes[0])
    assert fixed.is_winding_consistent
    assert fixed.volume > 0
