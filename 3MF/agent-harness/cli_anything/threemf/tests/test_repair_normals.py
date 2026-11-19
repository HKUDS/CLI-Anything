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


def _box(extent, center=(0, 0, 0), inverted=False):
    tm = trimesh.creation.box(extents=(extent, extent, extent))
    tm.apply_translation(center)
    if inverted:
        tm.invert()
    return tm


def _component_volumes(mesh):
    return sorted(part.volume for part in mesh_to_trimesh(mesh).split(only_watertight=False))


@pytest.mark.parametrize("invert_small", [False, True])
def test_disconnected_solids_are_oriented_independently(invert_small):
    small = _box(1, inverted=invert_small)
    large = _box(2, center=(5, 0, 0), inverted=not invert_small)
    mesh = _mesh(trimesh.util.concatenate([small, large]))
    attributes = tuple({"pid": "7", "p1": "0", "p2": "1", "p3": "2"} for _ in mesh.triangles)
    mesh = replace(mesh, triangle_attributes=attributes)
    original = mesh.triangles.copy()

    fixed, report = repair.repair_mesh(mesh)

    assert _component_volumes(fixed) == pytest.approx([1, 8])
    assert report["faces_reoriented"] == 12
    assert fixed.vertices.shape == mesh.vertices.shape
    for old_face, new_face, old_attrs, new_attrs in zip(
        mesh.triangles, fixed.triangles, attributes, fixed.triangle_attributes,
    ):
        assert _properties_by_vertex(old_face, old_attrs) == _properties_by_vertex(new_face, new_attrs)
    np.testing.assert_array_equal(mesh.triangles, original)


@pytest.mark.parametrize("inverted", [False, True])
def test_nested_closed_shells_retain_a_negative_cavity(inverted):
    outer = _box(4, inverted=inverted)
    cavity = _box(2, inverted=not inverted)
    mesh = _mesh(trimesh.util.concatenate([outer, cavity]))

    fixed, report = repair.repair_mesh(mesh)

    assert _component_volumes(fixed) == pytest.approx([-8, 64])
    assert mesh_to_trimesh(fixed).volume == pytest.approx(56)
    assert report["faces_reoriented"] == (24 if inverted else 0)


def test_nested_island_and_separate_solid_keep_material_void_parity():
    mesh = _mesh(trimesh.util.concatenate([
        _box(6), _box(4), _box(2), _box(8, center=(20, 0, 0), inverted=True),
    ]))

    fixed, report = repair.repair_mesh(mesh)

    assert _component_volumes(fixed) == pytest.approx([-64, 8, 216, 512])
    assert report["faces_reoriented"] == 24


def test_solid_in_a_ring_hole_is_not_mistaken_for_an_internal_cavity():
    ring = trimesh.creation.annulus(r_min=4, r_max=20, height=10, sections=64)
    mesh = _mesh(trimesh.util.concatenate([ring, _box(2, inverted=True)]))

    fixed, report = repair.repair_mesh(mesh)

    assert _component_volumes(fixed) == pytest.approx([8, ring.volume])
    assert report["faces_reoriented"] == 12


def _ring_with_intersecting_box(shape, reverse_order=False):
    ring = trimesh.creation.annulus(r_min=4, r_max=20, height=10, sections=64)
    if shape == "bridge":
        # Every vertex is in the washer material, but its long edges and
        # faces cross the bore. Vertex-only containment is insufficient.
        box = trimesh.creation.box(extents=(10, 2, 2))
        assert np.all(np.linalg.norm(box.vertices[:, :2], axis=1) > 4)
    else:
        center = (4, 0, 0) if shape == "straddling" else (5, 0, 0)
        box = _box(2, center=center)
    if reverse_order:
        box.faces = box.faces[::-1]
    return ring, box


@pytest.mark.parametrize("shape", ["straddling", "bridge", "touching"])
@pytest.mark.parametrize("reverse_order", [False, True])
def test_intersecting_or_touching_shells_are_not_inverted_as_cavities(shape, reverse_order):
    ring, box = _ring_with_intersecting_box(shape, reverse_order)
    mesh = _mesh(trimesh.util.concatenate([ring, box]))
    attributes = tuple({"pid": "7", "p1": "0", "p2": "1", "p3": "2"} for _ in mesh.triangles)
    mesh = replace(mesh, triangle_attributes=attributes)

    fixed, report = repair.repair_mesh(mesh)

    assert _component_volumes(fixed) == pytest.approx([box.volume, ring.volume])
    assert report["faces_reoriented"] == 0
    np.testing.assert_array_equal(fixed.vertices, mesh.vertices)
    np.testing.assert_array_equal(fixed.triangles, mesh.triangles)
    assert fixed.triangle_attributes == attributes


def test_disjoint_shell_inside_ring_material_is_still_a_cavity():
    ring = trimesh.creation.annulus(r_min=4, r_max=20, height=10, sections=64)
    mesh = _mesh(trimesh.util.concatenate([ring, _box(2, center=(8, 0, 0))]))

    fixed, report = repair.repair_mesh(mesh)

    assert _component_volumes(fixed) == pytest.approx([-8, ring.volume])
    assert report["faces_reoriented"] == 12


@pytest.mark.parametrize("scale", [1e-6, 1.0, 1e6])
@pytest.mark.parametrize("other, intersects", [
    ([[1.25, 1.25, 0], [2, 1.25, 0], [1.25, 2, 0]], False),
    ([[0, 2, 0], [2, 0, 0], [2, 2, 0]], True),
    ([[0.5, 0.5, -1], [0.5, 0.5, 1], [1.5, 0.5, 0]], True),
])
def test_boundary_intersection_handles_coplanar_and_crossing_triangles(scale, other, intersects):
    # The disjoint coplanar pair has overlapping AABBs. Separating only
    # along face normals and edge-cross-edge axes would report contact.
    first = np.array([[[0, 0, 0], [2, 0, 0], [0, 2, 0]]], dtype=float)
    second = np.array([other], dtype=float)
    translation = np.array([100, -50, 25]) * scale
    first = first * scale + translation
    second = second * scale + translation

    assert repair._shell_boundaries_intersect(first, second) is intersects
    assert repair._shell_boundaries_intersect(second, first) is intersects


@pytest.mark.parametrize("scale", [1e-6, 1.0, 1e6])
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_boundary_hierarchy_matches_exhaustive_triangle_pairs(scale, seed):
    rng = np.random.default_rng(seed)
    first = rng.uniform(-3, 3, (37, 1, 3)) + rng.normal(0, 0.2, (37, 3, 3))
    second = rng.uniform(-3, 3, (71, 1, 3)) + rng.normal(0, 0.2, (71, 3, 3))
    if seed == 0:
        second += 20
    elif seed == 1:
        # Coincident faces still count as contact when assigned to leaves.
        second[52] = first[13]
    else:
        # A long face reaches the first shell even though its center is far
        # away: partition centers must never replace full triangle bounds.
        first[7] = [[0, 0, 0], [2, 0, 0], [0, 2, 0]]
        second[63] = [[1, 1, -100], [1, 1, 100], [1, 100, 0]]
    translation = np.array([100, -50, 25]) * scale
    first = first * scale + translation
    second = second * scale + translation
    low = np.minimum(first.min(axis=(0, 1)), second.min(axis=(0, 1)))
    high = np.maximum(first.max(axis=(0, 1)), second.max(axis=(0, 1)))
    span = np.max(high - low)
    tolerance = 64 * np.finfo(float).eps
    # Bypass every bounding-box filter for the reference. The production
    # broad phase must reach every pair accepted by the unchanged SAT test.
    expected = any(
        repair._triangles_intersect(triangle, (second - low) / span, tolerance)
        for triangle in (first - low) / span
    )
    assert expected is (seed != 0)
    assert repair._shell_boundaries_intersect(first, second) is expected
    assert repair._shell_boundaries_intersect(second[::-1], first[::-1]) is expected


def test_high_resolution_nested_shells_preserve_geometry_and_cavity():
    outer = trimesh.creation.icosphere(subdivisions=4, radius=2)
    cavity = trimesh.creation.icosphere(subdivisions=4, radius=1)
    cavity.invert()
    mesh = _mesh(trimesh.util.concatenate([outer, cavity]))

    fixed, report = repair.repair_mesh(mesh)

    assert report["faces_reoriented"] == 0
    assert mesh_to_trimesh(fixed).volume == pytest.approx(outer.volume + cavity.volume)
    np.testing.assert_array_equal(fixed.vertices, mesh.vertices)
    np.testing.assert_array_equal(fixed.triangles, mesh.triangles)


def test_public_repair_preserves_an_intersecting_solid(tmp_path):
    source = tmp_path / "intersecting.3mf"
    destination = tmp_path / "repaired.3mf"
    ring, box = _ring_with_intersecting_box("straddling", reverse_order=True)
    _write(source, _mesh(trimesh.util.concatenate([ring, box])))

    result = CliRunner().invoke(cli, [
        "--json", "repair", str(source), "--output", str(destination),
    ])

    assert result.exit_code == 0, result.output
    fixed = parser.parse_3mf(str(destination)).meshes[0]
    assert _component_volumes(fixed) == pytest.approx([8, ring.volume])
    assert json.loads(result.output)["repairs"]["faces_reoriented"] == 0


def test_open_surface_does_not_prevent_closed_solid_normal_repair():
    box = _box(2, inverted=True)
    surface = trimesh.Trimesh(
        vertices=[[5, 0, 0], [5, 1, 0], [5, 0, 1]], faces=[[0, 1, 2]], process=False,
    )
    mesh = _mesh(trimesh.util.concatenate([box, surface]))

    fixed, report = repair.repair_mesh(mesh)

    solids = mesh_to_trimesh(fixed).split(only_watertight=True)
    assert len(solids) == 1
    assert solids[0].volume == pytest.approx(8)
    assert report["faces_reoriented"] == 12
    np.testing.assert_array_equal(fixed.triangles[-1], mesh.triangles[-1])


def test_public_repair_keeps_a_cavity_and_corrects_a_separate_solid(tmp_path):
    source = tmp_path / "mixed.3mf"
    destination = tmp_path / "repaired.3mf"
    _write(source, _mesh(trimesh.util.concatenate([
        _box(4), _box(2, inverted=True), _box(8, center=(20, 0, 0), inverted=True),
    ])))

    result = CliRunner().invoke(cli, [
        "--json", "repair", str(source), "--output", str(destination),
    ])

    assert result.exit_code == 0, result.output
    fixed = parser.parse_3mf(str(destination)).meshes[0]
    assert _component_volumes(fixed) == pytest.approx([-8, 64, 512])
    assert json.loads(result.output)["repairs"]["faces_reoriented"] == 12


def test_resize_auto_repair_orients_only_the_inverted_separate_solid(tmp_path):
    source = tmp_path / "washer-and-solid.3mf"
    destination = tmp_path / "resized.3mf"
    ring = trimesh.creation.annulus(r_min=4, r_max=20, height=10, sections=64)
    _write(source, _mesh(trimesh.util.concatenate([
        ring, _box(2, center=(30, 0, 0), inverted=True),
    ])))

    result = CliRunner().invoke(cli, [
        "--json", "resize", str(source), "--axis", "2", "--hole", "0",
        "--diameter", "10", "--output", str(destination),
    ])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["repairs"]["faces_reoriented"] == 12
    fixed = parser.parse_3mf(str(destination)).meshes[0]
    volumes = _component_volumes(fixed)
    assert len(volumes) == 2
    assert volumes[0] == pytest.approx(8)
    assert volumes[1] > 0


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
