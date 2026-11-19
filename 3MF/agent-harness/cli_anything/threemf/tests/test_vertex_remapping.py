"""Preserve geometry and properties when compacting duplicate vertex groups."""

import json
import subprocess
import sys
import zipfile

import numpy as np

from cli_anything.threemf.core.parser import MeshData, ThreeMFData, parse_3mf, write_3mf
from cli_anything.threemf.core.repair import merge_duplicate_vertices, repair_mesh


def _fixture(dtype=np.float64):
    vertices = np.array(
        [[9, 0, 0], [-2, 1, 0], [9, 0, 0], [0, 5, 0], [-2, 1, 0], [42, 42, 42]],
        dtype=dtype,
    )
    triangles = np.array([[2, 4, 3], [0, 1, 3], [2, 0, 4]], dtype=np.int32)
    return vertices, triangles


def test_merge_preserves_first_occurrence_order_and_inputs():
    for dtype in (np.float32, np.float64):
        for layout in ("C", "F", "strided"):
            vertices, triangles = _fixture(dtype)
            if layout == "F":
                vertices = np.asfortranarray(vertices)
                triangles = np.asfortranarray(triangles)
            elif layout == "strided":
                storage = np.empty((len(vertices), 6), dtype=dtype)
                storage[:, ::2] = vertices
                vertices = storage[:, ::2]
                triangles = triangles[:, ::-1]
            before_vertices, before_triangles = vertices.copy(), triangles.copy()
            vertices.flags.writeable = False
            triangles.flags.writeable = False

            unique, remapped, removed = merge_duplicate_vertices(vertices, triangles)

            expected = np.array([[0, 1, 2], [0, 1, 2], [0, 0, 1]], dtype=np.intp)
            if layout == "strided":
                expected = expected[:, ::-1]
            np.testing.assert_array_equal(unique, before_vertices[[0, 1, 3, 5]])
            np.testing.assert_array_equal(remapped, expected)
            np.testing.assert_array_equal(vertices, before_vertices)
            np.testing.assert_array_equal(triangles, before_triangles)
            assert unique.dtype == dtype
            assert remapped.dtype == np.dtype(np.intp)
            assert removed == 2


def test_merge_keeps_original_coordinates_and_rounding_parameter():
    vertices = np.array([[9.124, 0, 0], [-2, 1, 0], [9.123, 0, 0], [0, 5, 0]])
    triangles = np.array([[2, 1, 3]], dtype=np.int64)
    unique, remapped, removed = merge_duplicate_vertices(vertices, triangles, decimals=2)
    np.testing.assert_array_equal(unique, vertices[[0, 1, 3]])
    np.testing.assert_array_equal(remapped, [[0, 1, 2]])
    assert unique[0, 0] == 9.124
    assert removed == 1

    unique, remapped, removed = merge_duplicate_vertices(vertices, triangles, decimals=3)
    np.testing.assert_array_equal(unique, vertices)
    np.testing.assert_array_equal(remapped, triangles)
    assert removed == 0


def test_merge_handles_one_duplicate_group():
    vertices = np.tile([7.0, -1.0, 3.0], (5, 1))
    triangles = np.array([[4, 2, 0], [1, 3, 4]], dtype=np.int32)
    unique, remapped, removed = merge_duplicate_vertices(vertices, triangles)
    np.testing.assert_array_equal(unique, vertices[:1])
    np.testing.assert_array_equal(remapped, np.zeros_like(triangles))
    assert removed == 4


def test_merge_keeps_empty_triangle_shape_and_dtype():
    vertices, _ = _fixture()
    triangles = np.empty((0, 3), dtype=np.int32)
    unique, remapped, removed = merge_duplicate_vertices(vertices, triangles)
    np.testing.assert_array_equal(unique, vertices[[0, 1, 3, 5]])
    assert remapped.shape == (0, 3)
    assert remapped.dtype == triangles.dtype
    assert removed == 2


def test_merge_keeps_empty_vertex_arrays():
    vertices = np.empty((0, 3), dtype=np.float32)
    triangles = np.empty((0, 3), dtype=np.int32)
    unique, remapped, removed = merge_duplicate_vertices(vertices, triangles)
    assert unique is vertices
    assert remapped is triangles
    assert removed == 0


def test_repair_keeps_face_property_associations_and_report():
    vertices, triangles = _fixture()
    attributes = (
        {"pid": "7", "p1": "1", "p2": "2", "p3": "3"},
        {"pid": "8", "p1": "4", "p3": "6"},
        {"pid": "9", "p1": "0"},
    )
    mesh = MeshData("1", "groups", vertices, triangles, attributes)
    repaired, report = repair_mesh(mesh)
    np.testing.assert_array_equal(repaired.vertices, vertices[[0, 1, 3]])
    np.testing.assert_array_equal(repaired.triangles, [[0, 1, 2], [0, 1, 2]])
    assert repaired.triangle_attributes == attributes[:2]
    assert mesh.triangle_attributes == attributes
    assert report == {
        "vertices_merged": 2,
        "degenerate_faces_removed": 1,
        "unreferenced_vertices_removed": 1,
        "final_vertex_count": 3,
        "final_triangle_count": 2,
    }


def test_public_repair_preserves_archive_and_geometry(tmp_path):
    vertices, triangles = _fixture()
    marker = "{urn:vertex-remapping-test}marker"
    attributes = tuple({marker: value} for value in ("first", "second", "removed"))
    mesh = MeshData("1", "groups", vertices, triangles, attributes)
    data = ThreeMFData(
        meshes=(mesh,), unit="millimeter", model_path="3D/3dmodel.model",
        metadata={"Title": "Vertex groups"},
        raw_entries={"Metadata/settings.bin": b"preserved\x00settings"}, source_path="",
    )
    source, output = tmp_path / "source.3mf", tmp_path / "repaired.3mf"
    write_3mf(data, str(source))
    source_bytes = source.read_bytes()
    result = subprocess.run(
        [sys.executable, "-m", "cli_anything.threemf", "--json", "repair",
         str(source), "--output", str(output)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)["repairs"]
    assert report["vertices_merged"] == 2
    assert report["degenerate_faces_removed"] == 1
    assert report["unreferenced_vertices_removed"] == 1
    reloaded = parse_3mf(str(output))
    np.testing.assert_array_equal(reloaded.meshes[0].vertices, vertices[[0, 1, 3]])
    np.testing.assert_array_equal(reloaded.meshes[0].triangles, [[0, 1, 2], [0, 1, 2]])
    assert reloaded.meshes[0].triangle_attributes == attributes[:2]
    assert reloaded.metadata == data.metadata
    with zipfile.ZipFile(output) as archive:
        assert archive.read("Metadata/settings.bin") == b"preserved\x00settings"
    assert source.read_bytes() == source_bytes
