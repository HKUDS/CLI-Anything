"""Comprehensive unit tests for the 3MF core modules.

Covers:
- cli_anything.threemf.core.parser       (MeshData, ThreeMFData)
- cli_anything.threemf.utils.threemf_backend  (geometry utilities)
- cli_anything.threemf.core.inspector    (InspectParams, DetectedHole,
                                          inspect_mesh, compare_meshes)
- cli_anything.threemf.core.repair       (repair_mesh, merge_duplicate_vertices,
                                          remove_degenerate_faces,
                                          remove_unreferenced_vertices, fix_normals)
- cli_anything.threemf.core.modifier     (resize_holes, resize_single_hole)

All tests use synthetic numpy data -- no real .3mf files are required.
"""

from __future__ import annotations

import numpy as np
import pytest

from cli_anything.threemf.core.parser import MeshData, ThreeMFData
from cli_anything.threemf.utils import threemf_backend as backend
from cli_anything.threemf.core import inspector, repair, modifier
from cli_anything.threemf.core.inspector import DetectedHole, InspectParams
from cli_anything.threemf.core.modifier import resize_holes, resize_single_hole


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_cube_mesh(size: float = 10.0) -> MeshData:
    """Create a simple closed-cube MeshData for testing."""
    s = size / 2
    vertices = np.array(
        [
            [-s, -s, -s], [s, -s, -s], [s, s, -s], [-s, s, -s],
            [-s, -s,  s], [s, -s,  s], [s, s,  s], [-s, s,  s],
        ],
        dtype=np.float64,
    )
    triangles = np.array(
        [
            [0, 2, 1], [0, 3, 2],
            [4, 5, 6], [4, 6, 7],
            [0, 1, 5], [0, 5, 4],
            [2, 3, 7], [2, 7, 6],
            [0, 4, 7], [0, 7, 3],
            [1, 2, 6], [1, 6, 5],
        ],
        dtype=np.int32,
    )
    return MeshData(object_id="1", name="cube", vertices=vertices, triangles=triangles)


def _make_empty_mesh() -> MeshData:
    return MeshData(
        object_id="0",
        name="empty",
        vertices=np.empty((0, 3), dtype=np.float64),
        triangles=np.empty((0, 3), dtype=np.int32),
    )


def _make_threemf_data(mesh: MeshData | None = None) -> ThreeMFData:
    """Wrap a single mesh (or the default cube) in a ThreeMFData."""
    if mesh is None:
        mesh = _make_cube_mesh()
    return ThreeMFData(
        meshes=(mesh,),
        unit="millimeter",
        model_path="3D/3dmodel.model",
        metadata={"Author": "test"},
        raw_entries={},
        source_path="",
    )


def _make_circle_points(
    cx: float = 0.0, cy: float = 0.0, r: float = 5.0, n: int = 60
) -> np.ndarray:
    """Return (n, 2) points uniformly distributed on a circle."""
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.column_stack([cx + r * np.cos(theta), cy + r * np.sin(theta)])


def _make_mesh_with_duplicates() -> MeshData:
    """Cube with two duplicate vertices appended."""
    cube = _make_cube_mesh(4.0)
    extra = cube.vertices[:2].copy()
    vertices = np.vstack([cube.vertices, extra])
    triangles = np.vstack([
        cube.triangles,
        np.array([[8, 9, 2]], dtype=np.int32),
    ])
    return MeshData(object_id="dup", name="dup", vertices=vertices, triangles=triangles)


def _make_mesh_with_degenerate() -> MeshData:
    """Cube with one degenerate triangle (two identical indices) appended."""
    cube = _make_cube_mesh(4.0)
    degen = np.array([[0, 0, 1]], dtype=np.int32)
    triangles = np.vstack([cube.triangles, degen])
    return MeshData(object_id="deg", name="deg", vertices=cube.vertices, triangles=triangles)


def _make_fake_hole(
    center: tuple[float, float] = (0.0, 0.0),
    diameter: float = 3.0,
    hole_id: int = 0,
    axis: int = 0,
) -> DetectedHole:
    return DetectedHole(
        hole_id=hole_id,
        center=center,
        diameter=diameter,
        axis_min=-5.0,
        axis_max=5.0,
        axis=axis,
        confidence=0.9,
        vertex_count=10,
    )


# ===========================================================================
# TestParser -- MeshData and ThreeMFData
# ===========================================================================


class TestParser:
    """Tests for cli_anything.threemf.core.parser."""

    # --- MeshData construction -------------------------------------------------

    def test_mesh_data_basic_construction(self) -> None:
        """MeshData is created with correct attributes."""
        mesh = _make_cube_mesh()
        assert mesh.object_id == "1"
        assert mesh.name == "cube"
        assert mesh.vertices.shape == (8, 3)
        assert mesh.triangles.shape == (12, 3)

    def test_mesh_data_vertex_dtype(self) -> None:
        """Vertices array dtype is float64."""
        assert _make_cube_mesh().vertices.dtype == np.float64

    def test_mesh_data_triangle_dtype(self) -> None:
        """Triangles array dtype is int32."""
        assert _make_cube_mesh().triangles.dtype == np.int32

    def test_mesh_data_is_frozen_on_object_id(self) -> None:
        """MeshData raises FrozenInstanceError when object_id is reassigned."""
        mesh = _make_cube_mesh()
        with pytest.raises(Exception):
            mesh.object_id = "new_id"  # type: ignore[misc]

    def test_mesh_data_is_frozen_on_vertices(self) -> None:
        """MeshData raises FrozenInstanceError when vertices is reassigned."""
        mesh = _make_cube_mesh()
        with pytest.raises(Exception):
            mesh.vertices = np.zeros((8, 3))  # type: ignore[misc]

    def test_mesh_data_bad_vertex_shape_1d(self) -> None:
        """1-D vertex array raises ValueError."""
        flat = np.array([0.0, 1.0, 2.0])
        t = np.array([[0, 1, 2]], dtype=np.int32)
        with pytest.raises(ValueError, match="vertices"):
            MeshData(object_id="1", name="x", vertices=flat, triangles=t)  # type: ignore[arg-type]

    def test_mesh_data_bad_vertex_shape_wrong_columns(self) -> None:
        """Vertex array with 2 columns raises ValueError."""
        v = np.zeros((4, 2), dtype=np.float64)
        t = np.array([[0, 1, 2]], dtype=np.int32)
        with pytest.raises(ValueError, match="vertices"):
            MeshData(object_id="1", name="x", vertices=v, triangles=t)

    def test_mesh_data_bad_triangle_shape_wrong_columns(self) -> None:
        """Triangle array with 4 columns raises ValueError."""
        v = np.zeros((4, 3), dtype=np.float64)
        t = np.array([[0, 1, 2, 0]], dtype=np.int32)
        with pytest.raises(ValueError, match="triangles"):
            MeshData(object_id="1", name="x", vertices=v, triangles=t)

    def test_mesh_data_empty_name_is_allowed(self) -> None:
        """Empty name string is valid."""
        v = np.zeros((3, 3), dtype=np.float64)
        t = np.array([[0, 1, 2]], dtype=np.int32)
        mesh = MeshData(object_id="1", name="", vertices=v, triangles=t)
        assert mesh.name == ""

    def test_mesh_data_single_triangle(self) -> None:
        """A minimal mesh with one triangle can be constructed."""
        v = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float64)
        t = np.array([[0, 1, 2]], dtype=np.int32)
        mesh = MeshData(object_id="2", name="tri", vertices=v, triangles=t)
        assert mesh.triangles.shape == (1, 3)

    def test_mesh_data_empty_construction(self) -> None:
        """Empty mesh (0 vertices, 0 triangles) can be constructed."""
        m = _make_empty_mesh()
        assert m.vertices.shape == (0, 3)
        assert m.triangles.shape == (0, 3)

    # --- ThreeMFData construction -----------------------------------------------

    def test_threemf_data_stores_all_fields(self) -> None:
        """ThreeMFData stores all fields correctly."""
        data = _make_threemf_data()
        assert data.unit == "millimeter"
        assert data.model_path == "3D/3dmodel.model"
        assert data.metadata["Author"] == "test"
        assert len(data.meshes) == 1

    def test_threemf_data_is_frozen(self) -> None:
        """ThreeMFData raises FrozenInstanceError on attribute assignment."""
        data = _make_threemf_data()
        with pytest.raises(Exception):
            data.unit = "inch"  # type: ignore[misc]

    def test_threemf_data_multiple_meshes(self) -> None:
        """ThreeMFData can hold multiple meshes."""
        m1 = _make_cube_mesh(size=5.0)
        m2 = MeshData(
            object_id="2",
            name="small",
            vertices=np.zeros((3, 3), dtype=np.float64),
            triangles=np.array([[0, 1, 2]], dtype=np.int32),
        )
        data = ThreeMFData(
            meshes=(m1, m2),
            unit="millimeter",
            model_path="3D/3dmodel.model",
            metadata={},
            raw_entries={},
            source_path="",
        )
        assert len(data.meshes) == 2

    def test_threemf_data_empty_meshes(self) -> None:
        """ThreeMFData with no meshes is valid."""
        data = ThreeMFData(
            meshes=(),
            unit="millimeter",
            model_path="3D/3dmodel.model",
            metadata={},
            raw_entries={},
            source_path="",
        )
        assert len(data.meshes) == 0

    def test_threemf_data_raw_entries_preserved(self) -> None:
        """raw_entries bytes are stored unchanged."""
        payload = b"\x00\x01\x02\x03"
        data = ThreeMFData(
            meshes=(),
            unit="millimeter",
            model_path="3D/3dmodel.model",
            metadata={},
            raw_entries={"thumbnail.png": payload},
            source_path="",
        )
        assert data.raw_entries["thumbnail.png"] == payload


# ===========================================================================
# TestBackend -- threemf_backend geometry utilities
# ===========================================================================


class TestBackend:
    """Tests for cli_anything.threemf.utils.threemf_backend."""

    # --- mesh_to_trimesh -------------------------------------------------------

    def test_mesh_to_trimesh_returns_trimesh_instance(self) -> None:
        """mesh_to_trimesh returns a trimesh.Trimesh instance."""
        import trimesh
        tm = backend.mesh_to_trimesh(_make_cube_mesh())
        assert isinstance(tm, trimesh.Trimesh)

    def test_mesh_to_trimesh_vertex_count(self) -> None:
        """Converted trimesh has the same vertex count as MeshData."""
        mesh = _make_cube_mesh()
        assert backend.mesh_to_trimesh(mesh).vertices.shape[0] == mesh.vertices.shape[0]

    def test_mesh_to_trimesh_face_count(self) -> None:
        """Converted trimesh has the same face count as MeshData."""
        mesh = _make_cube_mesh()
        assert backend.mesh_to_trimesh(mesh).faces.shape[0] == mesh.triangles.shape[0]

    def test_mesh_to_trimesh_does_not_mutate_source(self) -> None:
        """mesh_to_trimesh does not mutate the original MeshData vertices."""
        mesh = _make_cube_mesh()
        orig = mesh.vertices.copy()
        tm = backend.mesh_to_trimesh(mesh)
        tm.vertices[0, 0] = 9999.0
        assert np.allclose(mesh.vertices, orig)

    # --- trimesh_to_mesh -------------------------------------------------------

    def test_trimesh_to_mesh_roundtrip_vertex_count(self) -> None:
        """trimesh -> MeshData preserves vertex count."""
        mesh = _make_cube_mesh()
        m2 = backend.trimesh_to_mesh(backend.mesh_to_trimesh(mesh), "1", "cube")
        assert m2.vertices.shape[0] == mesh.vertices.shape[0]

    def test_trimesh_to_mesh_roundtrip_face_count(self) -> None:
        """trimesh -> MeshData preserves face count."""
        mesh = _make_cube_mesh()
        m2 = backend.trimesh_to_mesh(backend.mesh_to_trimesh(mesh), "1", "cube")
        assert m2.triangles.shape[0] == mesh.triangles.shape[0]

    def test_trimesh_to_mesh_sets_object_id_and_name(self) -> None:
        """trimesh_to_mesh sets object_id and name correctly."""
        tm = backend.mesh_to_trimesh(_make_cube_mesh())
        m2 = backend.trimesh_to_mesh(tm, "42", "mymesh")
        assert m2.object_id == "42"
        assert m2.name == "mymesh"

    def test_trimesh_to_mesh_values_match(self) -> None:
        """Roundtrip preserves vertex coordinates."""
        mesh = _make_cube_mesh()
        tm = backend.mesh_to_trimesh(mesh)
        m2 = backend.trimesh_to_mesh(tm, "1", "cube")
        np.testing.assert_array_almost_equal(m2.vertices, mesh.vertices)

    # --- compute_mesh_stats ----------------------------------------------------

    def test_stats_vertex_count(self) -> None:
        assert compute_mesh_stats_cube()["vertex_count"] == 8

    def test_stats_face_count(self) -> None:
        assert compute_mesh_stats_cube()["face_count"] == 12

    def test_stats_watertight_closed_cube(self) -> None:
        assert compute_mesh_stats_cube()["watertight"] is True

    def test_stats_volume_cube_1000(self) -> None:
        stats = compute_mesh_stats_cube()
        assert stats["volume_mm3"] is not None
        assert abs(stats["volume_mm3"] - 1000.0) < 1.0

    def test_stats_bounding_box_has_required_keys(self) -> None:
        bb = compute_mesh_stats_cube()["bounding_box"]
        assert "min" in bb and "max" in bb and "size" in bb

    def test_stats_bounding_box_values_correct(self) -> None:
        bb = compute_mesh_stats_cube()["bounding_box"]
        assert np.allclose(bb["min"], [-5.0, -5.0, -5.0], atol=1e-6)
        assert np.allclose(bb["max"], [5.0, 5.0, 5.0], atol=1e-6)
        assert np.allclose(bb["size"], [10.0, 10.0, 10.0], atol=1e-6)

    def test_stats_surface_area_cube(self) -> None:
        stats = compute_mesh_stats_cube()
        assert abs(stats["surface_area_mm2"] - 600.0) < 5.0

    def test_stats_empty_mesh_defaults(self) -> None:
        """compute_mesh_stats handles an empty mesh gracefully."""
        stats = backend.compute_mesh_stats(_make_empty_mesh())
        assert stats["vertex_count"] == 0
        assert stats["face_count"] == 0
        assert stats["watertight"] is False
        assert stats["volume_mm3"] is None
        assert stats["surface_area_mm2"] == 0.0

    # --- fit_circle_least_squares ----------------------------------------------

    def test_fit_circle_perfect_center_and_radius(self) -> None:
        """fit_circle_least_squares recovers exact parameters of a perfect circle."""
        pts = _make_circle_points(cx=3.0, cy=2.0, r=5.0, n=100)
        cx, cy, r, err = backend.fit_circle_least_squares(pts)
        assert abs(cx - 3.0) < 1e-6
        assert abs(cy - 2.0) < 1e-6
        assert abs(r - 5.0) < 1e-6
        assert err < 1e-6

    def test_fit_circle_unit_circle(self) -> None:
        """fit_circle_least_squares works for unit circle at origin."""
        pts = _make_circle_points(cx=0.0, cy=0.0, r=1.0, n=60)
        cx, cy, r, _ = backend.fit_circle_least_squares(pts)
        assert abs(cx) < 1e-6
        assert abs(cy) < 1e-6
        assert abs(r - 1.0) < 1e-6

    def test_fit_circle_too_few_points(self) -> None:
        """fit_circle_least_squares raises ValueError for fewer than 3 points."""
        with pytest.raises(ValueError, match="At least 3"):
            backend.fit_circle_least_squares(np.array([[0.0, 0.0], [1.0, 0.0]]))

    def test_fit_circle_wrong_shape(self) -> None:
        """fit_circle_least_squares raises ValueError for (N,3) input."""
        pts = np.zeros((5, 3), dtype=np.float64)
        with pytest.raises(ValueError, match="points_2d must be"):
            backend.fit_circle_least_squares(pts)

    def test_fit_circle_noisy_stays_reasonable(self) -> None:
        """fit_circle_least_squares is robust to small noise."""
        rng = np.random.default_rng(42)
        pts = _make_circle_points(cx=1.0, cy=-1.0, r=3.0, n=80)
        pts = pts + rng.normal(0, 0.02, pts.shape)
        cx, cy, r, err = backend.fit_circle_least_squares(pts)
        assert abs(cx - 1.0) < 0.1
        assert abs(cy - (-1.0)) < 0.1
        assert abs(r - 3.0) < 0.1

    # --- find_cylinder_vertices ------------------------------------------------

    def test_find_cylinder_vertices_all_on_surface(self) -> None:
        """All points exactly on a cylinder surface are found."""
        theta = np.linspace(0, 2 * np.pi, 20, endpoint=False)
        r, cx, cy = 3.0, 1.0, 2.0
        x, y = cx + r * np.cos(theta), cy + r * np.sin(theta)
        verts = np.column_stack([np.zeros(20), x, y])  # axis=0
        idx = backend.find_cylinder_vertices(verts, np.array([cx, cy]), axis=0, radius=r, tolerance=0.01)
        assert len(idx) == 20

    def test_find_cylinder_vertices_none_found(self) -> None:
        """No vertices within tolerance returns empty array."""
        verts = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float64)
        idx = backend.find_cylinder_vertices(verts, np.array([100.0, 100.0]), axis=0, radius=5.0, tolerance=0.01)
        assert len(idx) == 0

    def test_find_cylinder_vertices_empty_input(self) -> None:
        """Empty vertex array returns empty index array."""
        idx = backend.find_cylinder_vertices(
            np.empty((0, 3), dtype=np.float64), np.array([0.0, 0.0]), axis=0, radius=3.0, tolerance=0.1
        )
        assert len(idx) == 0

    def test_find_cylinder_vertices_bad_axis(self) -> None:
        """Invalid axis raises ValueError."""
        with pytest.raises(ValueError, match="axis"):
            backend.find_cylinder_vertices(
                np.ones((5, 3)), np.array([0.0, 0.0]), axis=5, radius=1.0, tolerance=0.1
            )

    def test_find_cylinder_vertices_bad_center_shape(self) -> None:
        """center_yz with 3 elements raises ValueError."""
        with pytest.raises(ValueError, match="center_yz must have 2"):
            backend.find_cylinder_vertices(
                np.ones((5, 3)), np.array([0.0, 0.0, 0.0]), axis=0, radius=1.0, tolerance=0.1
            )

    # --- scale_vertices_radially -----------------------------------------------

    def test_scale_vertices_radially_reaches_new_radius(self) -> None:
        """Scaled vertices end up at the target radius."""
        theta = np.linspace(0, 2 * np.pi, 10, endpoint=False)
        verts = np.column_stack([np.zeros(10), 3.0 * np.cos(theta), 3.0 * np.sin(theta)])
        idx = np.arange(10, dtype=np.intp)
        new_verts = backend.scale_vertices_radially(verts, idx, np.array([0.0, 0.0]), axis=0, new_radius=5.0)
        actual_r = np.sqrt(new_verts[:, 1] ** 2 + new_verts[:, 2] ** 2)
        np.testing.assert_allclose(actual_r, 5.0, atol=1e-10)

    def test_scale_vertices_radially_does_not_mutate_input(self) -> None:
        """Original vertex array is never mutated."""
        verts = np.ones((6, 3), dtype=np.float64) * 3.0
        orig = verts.copy()
        backend.scale_vertices_radially(verts, np.arange(6, dtype=np.intp), np.array([0.0, 0.0]), axis=0, new_radius=7.0)
        assert np.allclose(verts, orig)

    def test_scale_vertices_radially_empty_indices_returns_copy(self) -> None:
        """Empty index array returns a copy of the original vertices."""
        verts = np.ones((4, 3), dtype=np.float64)
        new_verts = backend.scale_vertices_radially(
            verts, np.array([], dtype=np.intp), np.array([0.0, 0.0]), axis=0, new_radius=5.0
        )
        assert np.allclose(new_verts, verts)

    def test_scale_vertices_radially_bad_axis(self) -> None:
        """Invalid axis raises ValueError."""
        with pytest.raises(ValueError, match="axis"):
            backend.scale_vertices_radially(
                np.ones((4, 3)), np.arange(4, dtype=np.intp), np.array([0.0, 0.0]), axis=9, new_radius=1.0
            )

    def test_scale_vertices_radially_preserves_axis_coordinate(self) -> None:
        """The axis coordinate is unchanged after radial scaling."""
        z = np.linspace(-5, 5, 8)
        x = 3.0 * np.cos(np.linspace(0, 2 * np.pi, 8, endpoint=False))
        y = 3.0 * np.sin(np.linspace(0, 2 * np.pi, 8, endpoint=False))
        verts = np.column_stack([x, y, z])  # axis=2
        idx = np.arange(8, dtype=np.intp)
        new_verts = backend.scale_vertices_radially(verts, idx, np.array([0.0, 0.0]), axis=2, new_radius=7.0)
        assert np.allclose(new_verts[:, 2], z)

    # --- cross_section_circles (smoke tests) -----------------------------------

    def test_cross_section_circles_returns_list(self) -> None:
        circles = backend.cross_section_circles(_make_cube_mesh(), axis=0, num_planes=5)
        assert isinstance(circles, list)

    def test_cross_section_circles_empty_mesh(self) -> None:
        circles = backend.cross_section_circles(_make_empty_mesh(), axis=0, num_planes=5)
        assert circles == []

    def test_cross_section_circles_bad_axis(self) -> None:
        with pytest.raises(ValueError, match="axis"):
            backend.cross_section_circles(_make_cube_mesh(), axis=5, num_planes=5)


# Convenience function used in multiple TestBackend tests
def compute_mesh_stats_cube() -> dict:
    return backend.compute_mesh_stats(_make_cube_mesh(size=10.0))


# ===========================================================================
# TestInspector -- InspectParams, DetectedHole, inspect_mesh, compare_meshes
# ===========================================================================


class TestInspector:
    """Tests for cli_anything.threemf.core.inspector."""

    # --- InspectParams ---------------------------------------------------------

    def test_inspect_params_default_values(self) -> None:
        p = inspector.InspectParams()
        assert p.num_planes == 20
        assert p.min_hole_diameter == 0.5
        assert p.min_confidence == 0.7
        assert p.axis == 0

    def test_inspect_params_custom_values(self) -> None:
        p = inspector.InspectParams(num_planes=10, min_hole_diameter=1.0, min_confidence=0.8, axis=2)
        assert p.num_planes == 10
        assert p.min_confidence == 0.8
        assert p.axis == 2

    def test_inspect_params_is_frozen(self) -> None:
        p = inspector.InspectParams()
        with pytest.raises(Exception):
            p.num_planes = 99  # type: ignore[misc]

    # --- DetectedHole ----------------------------------------------------------

    def test_detected_hole_stores_all_fields(self) -> None:
        h = inspector.DetectedHole(
            hole_id=5, center=(1.0, 2.0), diameter=3.5,
            axis_min=-5.0, axis_max=5.0, axis=1, confidence=0.85, vertex_count=30,
        )
        assert h.hole_id == 5
        assert h.center == (1.0, 2.0)
        assert h.diameter == 3.5
        assert h.axis == 1
        assert h.confidence == 0.85
        assert h.vertex_count == 30

    def test_detected_hole_is_frozen(self) -> None:
        h = _make_fake_hole()
        with pytest.raises(Exception):
            h.hole_id = 99  # type: ignore[misc]

    # --- inspect_mesh ----------------------------------------------------------

    def test_inspect_mesh_returns_list(self) -> None:
        assert isinstance(inspector.inspect_mesh(_make_cube_mesh()), list)

    def test_inspect_mesh_empty_mesh_returns_empty_list(self) -> None:
        assert inspector.inspect_mesh(_make_empty_mesh()) == []

    def test_inspect_mesh_default_params(self) -> None:
        """inspect_mesh runs with None params (uses defaults)."""
        result = inspector.inspect_mesh(_make_cube_mesh(), None)
        assert isinstance(result, list)

    def test_inspect_mesh_custom_params(self) -> None:
        """inspect_mesh accepts custom InspectParams without error."""
        params = inspector.InspectParams(num_planes=5, min_hole_diameter=1.0)
        result = inspector.inspect_mesh(_make_cube_mesh(), params)
        assert isinstance(result, list)

    def test_inspect_mesh_result_items_are_detected_holes(self) -> None:
        """Any items in the result are DetectedHole instances."""
        for item in inspector.inspect_mesh(_make_cube_mesh()):
            assert isinstance(item, inspector.DetectedHole)

    def test_inspect_mesh_sorted_by_hole_id(self) -> None:
        """Results are sorted by hole_id in ascending order."""
        result = inspector.inspect_mesh(_make_cube_mesh())
        ids = [h.hole_id for h in result]
        assert ids == sorted(ids)

    # --- compare_meshes --------------------------------------------------------

    def test_compare_meshes_identical_zero_diff(self) -> None:
        mesh = _make_cube_mesh()
        result = inspector.compare_meshes(mesh, mesh)
        assert result["vertices"]["diff"] == 0
        assert result["faces"]["diff"] == 0
        assert result["volume"]["diff"] == pytest.approx(0.0, abs=1e-6)

    def test_compare_meshes_has_required_top_level_keys(self) -> None:
        result = inspector.compare_meshes(_make_cube_mesh(), _make_cube_mesh())
        for key in ("vertices", "faces", "volume", "watertight"):
            assert key in result

    def test_compare_meshes_sub_dicts_have_file1_file2_diff(self) -> None:
        result = inspector.compare_meshes(_make_cube_mesh(), _make_cube_mesh())
        for key in ("vertices", "faces", "volume"):
            sub = result[key]
            assert "file1" in sub and "file2" in sub and "diff" in sub

    def test_compare_meshes_watertight_has_file1_and_file2(self) -> None:
        result = inspector.compare_meshes(_make_cube_mesh(), _make_cube_mesh())
        assert "file1" in result["watertight"] and "file2" in result["watertight"]

    def test_compare_meshes_vertex_counts_match_meshes(self) -> None:
        mesh_a = _make_cube_mesh(size=10.0)
        mesh_b = _make_cube_mesh(size=5.0)
        result = inspector.compare_meshes(mesh_a, mesh_b)
        assert result["vertices"]["file1"] == mesh_a.vertices.shape[0]
        assert result["vertices"]["file2"] == mesh_b.vertices.shape[0]

    def test_compare_meshes_different_volumes(self) -> None:
        """Cubes of different sizes have different volumes."""
        mesh_a = _make_cube_mesh(size=10.0)
        mesh_b = _make_cube_mesh(size=20.0)
        result = inspector.compare_meshes(mesh_a, mesh_b)
        assert result["volume"]["file2"] > result["volume"]["file1"]

    # --- get_mesh_info ---------------------------------------------------------

    def test_get_mesh_info_returns_dict(self) -> None:
        """get_mesh_info returns a dict."""
        result = inspector.get_mesh_info(_make_cube_mesh())
        assert isinstance(result, dict)

    def test_get_mesh_info_has_object_id_and_name(self) -> None:
        """get_mesh_info includes object_id and name fields."""
        mesh = _make_cube_mesh()
        result = inspector.get_mesh_info(mesh)
        assert result["object_id"] == mesh.object_id
        assert result["name"] == mesh.name

    def test_get_mesh_info_vertex_and_triangle_counts(self) -> None:
        """get_mesh_info reports correct vertex and triangle counts."""
        mesh = _make_cube_mesh()
        result = inspector.get_mesh_info(mesh)
        assert result["num_vertices"] == 8
        assert result["num_triangles"] == 12

    def test_get_mesh_info_includes_stats_keys(self) -> None:
        """get_mesh_info includes all keys from compute_mesh_stats."""
        result = inspector.get_mesh_info(_make_cube_mesh())
        for key in ("vertex_count", "face_count", "bounding_box", "watertight",
                    "volume_mm3", "surface_area_mm2"):
            assert key in result

    # --- _validate_mesh error branches -----------------------------------------

    def test_validate_mesh_raises_for_none(self) -> None:
        """compare_meshes propagates ValueError when mesh_data is None."""
        with pytest.raises((ValueError, AttributeError)):
            inspector.compare_meshes(None, _make_cube_mesh())  # type: ignore[arg-type]

    # --- inspect_mesh flat-mesh early return -----------------------------------

    def test_inspect_mesh_flat_mesh_returns_empty(self) -> None:
        """A mesh with all vertices on a single plane (zero span along axis) returns []."""
        # All vertices share the same X coordinate -> span along X=0 is zero
        v = np.array(
            [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 1.0]],
            dtype=np.float64,
        )
        t = np.array([[0, 1, 2], [1, 3, 2]], dtype=np.int32)
        mesh = MeshData(object_id="1", name="flat", vertices=v, triangles=t)
        params = inspector.InspectParams(axis=0)
        result = inspector.inspect_mesh(mesh, params)
        assert result == []


# ===========================================================================
# TestRepair -- repair_mesh, individual repair functions, fix_normals
# ===========================================================================


class TestRepair:
    """Tests for cli_anything.threemf.core.repair."""

    # --- repair_mesh -----------------------------------------------------------

    def test_repair_mesh_returns_tuple_of_mesh_and_dict(self) -> None:
        result = repair.repair_mesh(_make_cube_mesh())
        assert isinstance(result, tuple) and len(result) == 2
        assert isinstance(result[0], MeshData)
        assert isinstance(result[1], dict)

    def test_repair_mesh_report_has_required_keys(self) -> None:
        _, report = repair.repair_mesh(_make_cube_mesh())
        for key in (
            "vertices_merged", "degenerate_faces_removed",
            "unreferenced_vertices_removed", "final_vertex_count", "final_triangle_count",
        ):
            assert key in report

    def test_repair_clean_mesh_zero_changes(self) -> None:
        _, report = repair.repair_mesh(_make_cube_mesh())
        assert report["vertices_merged"] == 0
        assert report["degenerate_faces_removed"] == 0
        assert report["unreferenced_vertices_removed"] == 0

    def test_repair_final_counts_match_returned_mesh(self) -> None:
        repaired, report = repair.repair_mesh(_make_cube_mesh())
        assert report["final_vertex_count"] == repaired.vertices.shape[0]
        assert report["final_triangle_count"] == repaired.triangles.shape[0]

    def test_repair_empty_mesh_returns_same_object(self) -> None:
        m = _make_empty_mesh()
        repaired, report = repair.repair_mesh(m)
        assert repaired is m
        assert report["vertices_merged"] == 0

    def test_repair_merges_duplicate_vertices(self) -> None:
        m = _make_mesh_with_duplicates()
        _, report = repair.repair_mesh(m)
        assert report["vertices_merged"] >= 1

    def test_repair_removes_degenerate_faces(self) -> None:
        m = _make_mesh_with_degenerate()
        _, report = repair.repair_mesh(m)
        assert report["degenerate_faces_removed"] >= 1

    def test_repair_full_pipeline_vertex_count_non_increasing(self) -> None:
        """After repair, vertex count is <= original."""
        m = _make_mesh_with_duplicates()
        repaired, _ = repair.repair_mesh(m)
        assert repaired.vertices.shape[0] <= m.vertices.shape[0]

    # --- merge_duplicate_vertices ----------------------------------------------

    def test_merge_duplicate_vertices_removes_one(self) -> None:
        v = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            dtype=np.float64,
        )
        t = np.array([[0, 1, 3]], dtype=np.int32)
        _, _, count = repair.merge_duplicate_vertices(v, t)
        assert count == 1

    def test_merge_duplicate_vertices_no_duplicates_count_zero(self) -> None:
        m = _make_cube_mesh()
        _, _, count = repair.merge_duplicate_vertices(m.vertices, m.triangles)
        assert count == 0

    def test_merge_duplicate_vertices_empty(self) -> None:
        _, _, count = repair.merge_duplicate_vertices(
            np.empty((0, 3), dtype=np.float64), np.empty((0, 3), dtype=np.int32)
        )
        assert count == 0

    def test_merge_duplicate_vertices_cube_duplicates(self) -> None:
        m = _make_mesh_with_duplicates()
        v2, _, count = repair.merge_duplicate_vertices(m.vertices, m.triangles)
        assert count == 2
        assert v2.shape[0] == m.vertices.shape[0] - 2

    # --- remove_degenerate_faces -----------------------------------------------

    def test_remove_degenerate_faces_removes_three(self) -> None:
        t = np.array(
            [[0, 1, 2], [0, 0, 2], [1, 2, 1], [3, 4, 3], [5, 6, 7]],
            dtype=np.int32,
        )
        t2, count = repair.remove_degenerate_faces(t)
        assert count == 3
        assert t2.shape[0] == 2

    def test_remove_degenerate_faces_all_valid(self) -> None:
        t = np.array([[0, 1, 2], [3, 4, 5]], dtype=np.int32)
        _, count = repair.remove_degenerate_faces(t)
        assert count == 0

    def test_remove_degenerate_faces_empty(self) -> None:
        t2, count = repair.remove_degenerate_faces(np.empty((0, 3), dtype=np.int32))
        assert count == 0 and t2.shape[0] == 0

    def test_remove_degenerate_faces_cube_with_one(self) -> None:
        m = _make_mesh_with_degenerate()
        _, count = repair.remove_degenerate_faces(m.triangles)
        assert count == 1

    # --- remove_unreferenced_vertices ------------------------------------------

    def test_remove_unreferenced_removes_one(self) -> None:
        m = _make_cube_mesh()
        extra = np.array([[99.0, 99.0, 99.0]], dtype=np.float64)
        v = np.vstack([m.vertices, extra])
        _, _, count = repair.remove_unreferenced_vertices(v, m.triangles)
        assert count == 1

    def test_remove_unreferenced_all_referenced_count_zero(self) -> None:
        m = _make_cube_mesh()
        _, _, count = repair.remove_unreferenced_vertices(m.vertices, m.triangles)
        assert count == 0

    def test_remove_unreferenced_no_triangles_removes_all(self) -> None:
        v = np.zeros((4, 3), dtype=np.float64)
        _, _, count = repair.remove_unreferenced_vertices(v, np.empty((0, 3), dtype=np.int32))
        assert count == 4

    def test_remove_unreferenced_remaps_indices_validly(self) -> None:
        """After removal, triangle indices are still valid for the new vertex array."""
        v = np.array(
            [[0.0, 0.0, 0.0], [99.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            dtype=np.float64,
        )
        t = np.array([[0, 2, 3]], dtype=np.int32)
        v2, t2, _ = repair.remove_unreferenced_vertices(v, t)
        assert t2.max() < v2.shape[0]

    def test_remove_unreferenced_empty_vertices(self) -> None:
        _, _, count = repair.remove_unreferenced_vertices(
            np.empty((0, 3), dtype=np.float64), np.empty((0, 3), dtype=np.int32)
        )
        assert count == 0

    # --- fix_normals -----------------------------------------------------------

    def test_fix_normals_returns_mesh_data(self) -> None:
        assert isinstance(repair.fix_normals(_make_cube_mesh()), MeshData)

    def test_fix_normals_preserves_vertex_count(self) -> None:
        mesh = _make_cube_mesh()
        assert repair.fix_normals(mesh).vertices.shape[0] == mesh.vertices.shape[0]

    def test_fix_normals_preserves_face_count(self) -> None:
        mesh = _make_cube_mesh()
        assert repair.fix_normals(mesh).triangles.shape[0] == mesh.triangles.shape[0]

    def test_fix_normals_empty_mesh_passthrough(self) -> None:
        """fix_normals returns the same object for an empty mesh."""
        m = _make_empty_mesh()
        assert repair.fix_normals(m) is m


# ===========================================================================
# TestModifier -- resize_holes, resize_single_hole
# ===========================================================================


class TestModifier:
    """Tests for cli_anything.threemf.core.modifier."""

    # --- resize_holes validation -----------------------------------------------

    def test_resize_holes_bad_mesh_index_raises(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            resize_holes(_make_threemf_data(), [0], 5.0, mesh_index=99)

    def test_resize_holes_negative_diameter_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            resize_holes(_make_threemf_data(), [0], -1.0, mesh_index=0)

    def test_resize_holes_zero_diameter_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            resize_holes(_make_threemf_data(), [0], 0.0, mesh_index=0)

    def test_resize_holes_empty_hole_ids_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            resize_holes(_make_threemf_data(), [], 5.0, mesh_index=0)

    def test_resize_holes_unknown_hole_id_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown hole_ids"):
            resize_holes(_make_threemf_data(), [999], 5.0, mesh_index=0)

    def test_resize_holes_none_data_raises(self) -> None:
        with pytest.raises((ValueError, AttributeError)):
            resize_holes(None, [0], 5.0, mesh_index=0)  # type: ignore[arg-type]

    # --- resize_single_hole ----------------------------------------------------

    def test_resize_single_hole_returns_tuple(self) -> None:
        result = resize_single_hole(_make_cube_mesh(), _make_fake_hole(), 4.0)
        assert isinstance(result, tuple) and len(result) == 2

    def test_resize_single_hole_first_element_is_mesh_data(self) -> None:
        new_mesh, _ = resize_single_hole(_make_cube_mesh(), _make_fake_hole(), 4.0)
        assert isinstance(new_mesh, MeshData)

    def test_resize_single_hole_report_has_required_keys(self) -> None:
        _, report = resize_single_hole(_make_cube_mesh(), _make_fake_hole(), 4.0)
        for key in ("hole_id", "old_diameter", "new_diameter", "vertices_moved"):
            assert key in report

    def test_resize_single_hole_report_new_diameter_correct(self) -> None:
        _, report = resize_single_hole(_make_cube_mesh(), _make_fake_hole(diameter=3.0), 6.0)
        assert report["new_diameter"] == pytest.approx(6.0, abs=1e-4)

    def test_resize_single_hole_report_old_diameter_correct(self) -> None:
        _, report = resize_single_hole(_make_cube_mesh(), _make_fake_hole(diameter=3.5, hole_id=2), 5.0)
        assert report["old_diameter"] == 3.5
        assert report["hole_id"] == 2

    def test_resize_single_hole_negative_diameter_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            resize_single_hole(_make_cube_mesh(), _make_fake_hole(), -5.0)

    def test_resize_single_hole_none_mesh_raises(self) -> None:
        with pytest.raises((ValueError, AttributeError)):
            resize_single_hole(None, _make_fake_hole(), 5.0)  # type: ignore[arg-type]

    def test_resize_single_hole_no_wall_vertices_returns_unchanged_mesh(self) -> None:
        """If no wall vertices match (hole centre far away), mesh is unchanged."""
        mesh = _make_cube_mesh()
        hole = _make_fake_hole(center=(500.0, 500.0))
        new_mesh, report = resize_single_hole(mesh, hole, 4.0)
        assert report["vertices_moved"] == 0
        assert new_mesh is mesh

    def test_resize_single_hole_does_not_mutate_original_vertices(self) -> None:
        """resize_single_hole never mutates the input MeshData."""
        n = 20
        theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
        r = 1.0
        verts = np.column_stack([np.zeros(n), r * np.cos(theta), r * np.sin(theta)])
        tris = np.array([[i, (i + 1) % n, (i + 2) % n] for i in range(n - 2)], dtype=np.int32)
        mesh = MeshData(object_id="c", name="c", vertices=verts, triangles=tris)
        original = mesh.vertices.copy()
        hole = inspector.DetectedHole(
            hole_id=0, center=(0.0, 0.0), diameter=r * 2,
            axis_min=-0.1, axis_max=0.1, axis=0,
            confidence=0.9, vertex_count=n,
        )
        resize_single_hole(mesh, hole, target_diameter=3.0)
        np.testing.assert_array_equal(mesh.vertices, original)
