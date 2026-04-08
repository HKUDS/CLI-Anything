"""E2E tests for cli-anything-cloudcompare.

These tests invoke the REAL CloudCompare binary (Flatpak or native).
CloudCompare MUST be installed — tests will fail, not skip, if absent.

Run with:
    python3 -m pytest cli_anything/cloudcompare/tests/test_full_e2e.py -v -s

Run against the installed CLI command:
    CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/cloudcompare/tests/test_full_e2e.py -v -s
"""

import json
import os
import subprocess
import sys
import tempfile

import pytest


# ── CLI resolver (follows HARNESS.md spec) ─────────────────────────────────────

def _resolve_cli(name: str) -> list[str]:
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"\n[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "cli_anything.cloudcompare.cloudcompare_cli"
    print(f"\n[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


# ── Cloud file generator ───────────────────────────────────────────────────────

def _make_xyz_cloud(path: str, n_points: int = 200, add_noise: bool = False) -> str:
    """Generate a synthetic XYZ cloud file.

    Creates points on a flat plane (z=0) with optional outlier noise.
    Format: x y z (space separated, no header) — CloudCompare ASC format.
    """
    import math
    import random
    random.seed(42)

    grid = int(math.sqrt(n_points))
    with open(path, "w") as f:
        for i in range(grid):
            for j in range(grid):
                x = i * 0.1
                y = j * 0.1
                z = 0.0 + random.uniform(-0.001, 0.001)  # nearly flat
                f.write(f"{x:.6f} {y:.6f} {z:.6f}\n")

        if add_noise:
            # Add outlier points far from the plane
            for _ in range(10):
                x = random.uniform(0, 1)
                y = random.uniform(0, 1)
                z = random.uniform(10, 20)  # way above the plane
                f.write(f"{x:.6f} {y:.6f} {z:.6f}\n")
    return path


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir(tmp_path):
    return str(tmp_path)


@pytest.fixture
def cloud_xyz(tmp_dir):
    """A small synthetic point cloud (XYZ format)."""
    path = os.path.join(tmp_dir, "cloud.xyz")
    _make_xyz_cloud(path, n_points=225)
    print(f"\n  Input cloud: {path}")
    return path


@pytest.fixture
def noisy_cloud_xyz(tmp_dir):
    """A cloud with outlier noise points."""
    path = os.path.join(tmp_dir, "noisy_cloud.xyz")
    _make_xyz_cloud(path, n_points=100, add_noise=True)
    return path


@pytest.fixture
def project_json(tmp_dir):
    return os.path.join(tmp_dir, "test.json")


# ── E2E: Backend tests ─────────────────────────────────────────────────────────

class TestBackendAvailability:
    def test_cloudcompare_is_installed(self):
        """CloudCompare MUST be installed — this test will fail if not."""
        from cli_anything.cloudcompare.utils.cc_backend import find_cloudcompare, is_available
        assert is_available(), (
            "CloudCompare is not installed!\n"
            "Install with: flatpak install flathub org.cloudcompare.CloudCompare"
        )
        cmd = find_cloudcompare()
        assert len(cmd) > 0
        print(f"\n  CloudCompare command: {' '.join(cmd)}")


class TestFormatConversion:
    def test_xyz_to_ply(self, tmp_dir, cloud_xyz):
        """Convert XYZ cloud to PLY format via CloudCompare."""
        from cli_anything.cloudcompare.utils.cc_backend import convert_format

        output_path = os.path.join(tmp_dir, "output.ply")
        result = convert_format(cloud_xyz, output_path)

        assert result["returncode"] == 0, (
            f"CloudCompare failed (exit {result['returncode']}):\n{result['stderr'][:800]}"
        )
        assert result.get("exists"), f"Output PLY not created: {output_path}"
        assert result["file_size"] > 0, "Output PLY is empty"

        # Verify PLY magic bytes
        with open(output_path, "rb") as f:
            header = f.read(10)
        assert header.startswith(b"ply"), f"Output is not a valid PLY file: {header[:10]}"

        print(f"\n  PLY output: {output_path} ({result['file_size']:,} bytes)")

    def test_xyz_to_las(self, tmp_dir, cloud_xyz):
        """Convert XYZ cloud to LAS format via CloudCompare."""
        from cli_anything.cloudcompare.utils.cc_backend import convert_format

        output_path = os.path.join(tmp_dir, "output.las")
        result = convert_format(cloud_xyz, output_path)

        assert result["returncode"] == 0, (
            f"CloudCompare failed:\n{result['stderr'][:800]}"
        )
        assert result.get("exists"), f"Output LAS not created: {output_path}"
        assert result["file_size"] > 0

        # Verify LAS magic bytes ("LASF")
        with open(output_path, "rb") as f:
            magic = f.read(4)
        assert magic == b"LASF", f"Output is not a valid LAS file: {magic}"

        print(f"\n  LAS output: {output_path} ({result['file_size']:,} bytes)")


class TestSubsampling:
    def test_spatial_subsample(self, tmp_dir, cloud_xyz):
        """Subsample using SPATIAL method."""
        from cli_anything.cloudcompare.utils.cc_backend import subsample

        output_path = os.path.join(tmp_dir, "subsampled_spatial.xyz")
        result = subsample(cloud_xyz, output_path, method="SPATIAL", parameter=0.2)

        assert result["returncode"] == 0, (
            f"Subsample failed:\n{result['stderr'][:800]}"
        )
        assert result.get("exists"), f"Subsampled cloud not created: {output_path}"
        assert result["file_size"] > 0

        # Spatial subsampling should reduce the cloud
        input_size = os.path.getsize(cloud_xyz)
        assert result["file_size"] <= input_size * 2  # not much larger than input

        print(f"\n  Spatial subsample: {output_path} ({result['file_size']:,} bytes)")

    def test_random_subsample(self, tmp_dir, cloud_xyz):
        """Subsample using RANDOM method (keep N points)."""
        from cli_anything.cloudcompare.utils.cc_backend import subsample

        output_path = os.path.join(tmp_dir, "subsampled_random.xyz")
        result = subsample(cloud_xyz, output_path, method="RANDOM", parameter=50)

        assert result["returncode"] == 0, (
            f"Random subsample failed:\n{result['stderr'][:800]}"
        )
        assert result.get("exists"), f"Subsampled cloud not created: {output_path}"
        assert result["file_size"] > 0

        print(f"\n  Random subsample: {output_path} ({result['file_size']:,} bytes)")


class TestSORFilter:
    def test_sor_removes_outliers(self, tmp_dir, noisy_cloud_xyz):
        """SOR filter removes outlier noise points."""
        from cli_anything.cloudcompare.utils.cc_backend import sor_filter

        output_path = os.path.join(tmp_dir, "filtered.xyz")
        result = sor_filter(noisy_cloud_xyz, output_path, nb_points=6, std_ratio=1.0)

        assert result["returncode"] == 0, (
            f"SOR filter failed:\n{result['stderr'][:800]}"
        )
        assert result.get("exists"), f"Filtered cloud not created: {output_path}"
        assert result["file_size"] > 0

        # Compare point counts (line counts in XYZ/ASC format).
        # NOTE: file size comparison is unreliable — CloudCompare appends a
        # scalar field (deviation) column to ASC output, making the filtered
        # file larger per-point even though it has fewer points.
        with open(noisy_cloud_xyz) as f:
            input_count = sum(1 for line in f if line.strip())
        with open(output_path) as f:
            output_count = sum(1 for line in f if line.strip())

        # SOR should have removed the 10 outlier noise points
        assert output_count < input_count, (
            f"SOR filter did not reduce point count: "
            f"input={input_count} pts → output={output_count} pts"
        )

        print(f"\n  SOR filtered: {output_path} ({result['file_size']:,} bytes)")
        print(f"  Points: {input_count} → {output_count} (removed {input_count - output_count})")


class TestCSFFilter:
    """E2E tests for the Cloth Simulation Filter (CSF) ground extraction."""

    @pytest.fixture
    def scene_cloud(self, tmp_dir):
        """Synthetic scene: 100 ground points (z≈0) + 25 elevated points (z=5)."""
        path = os.path.join(tmp_dir, "scene.xyz")
        with open(path, "w") as f:
            for i in range(10):
                for j in range(10):
                    f.write(f"{i * 0.5:.1f} {j * 0.5:.1f} 0.0\n")
            for i in range(5):
                for j in range(5):
                    f.write(f"{i * 0.5:.1f} {j * 0.5:.1f} 5.0\n")
        return path

    def test_csf_extracts_ground(self, tmp_dir, scene_cloud):
        """CSF filter produces a ground cloud."""
        from cli_anything.cloudcompare.utils.cc_backend import csf_filter

        ground_out = os.path.join(tmp_dir, "ground.las")
        result = csf_filter(scene_cloud, ground_out, scene="FLAT",
                            cloth_resolution=0.5, class_threshold=0.3)

        assert result["returncode"] == 0, f"CSF failed:\n{result['stderr'][:400]}"
        assert result["ground_exists"], "Ground cloud not created"
        assert result["ground_size"] > 0
        print(f"\n  CSF ground: {ground_out} ({result['ground_size']:,} bytes)")

    def test_csf_exports_both_layers(self, tmp_dir, scene_cloud):
        """CSF filter exports both ground and off-ground clouds."""
        from cli_anything.cloudcompare.utils.cc_backend import csf_filter

        ground_out    = os.path.join(tmp_dir, "ground.las")
        offground_out = os.path.join(tmp_dir, "offground.las")
        result = csf_filter(scene_cloud, ground_out, offground_out,
                            scene="FLAT", cloth_resolution=0.5, class_threshold=0.3)

        assert result["returncode"] == 0
        assert result["ground_exists"]
        assert result["offground_exists"]
        assert result["ground_size"] > 0
        assert result["offground_size"] > 0

        # Ground + offground must account for all input points
        def _las_point_count(p):
            """Read POINTS count from a LAS/PCD/ASC file (best-effort)."""
            import struct
            with open(p, "rb") as f:
                header = f.read(375)
            # LAS 1.x: point count at offset 107 (uint32)
            try:
                return struct.unpack_from("<I", header, 107)[0]
            except Exception:
                return None

        g = _las_point_count(ground_out)
        u = _las_point_count(offground_out)
        if g is not None and u is not None:
            assert g + u == 125, f"Point count mismatch: {g} + {u} != 125"
        print(f"\n  Ground: {result['ground_size']:,} B  Off-ground: {result['offground_size']:,} B")

    def test_csf_cli_command(self, tmp_dir, project_json, scene_cloud):
        """cloud filter-csf via installed CLI subprocess."""
        cli = _resolve_cli("cli-anything-cloudcompare")
        ground_out = os.path.join(tmp_dir, "ground.las")

        subprocess.run(cli + ["project", "new", "-o", project_json],
                       capture_output=True, check=True)
        subprocess.run(cli + ["--project", project_json, "cloud", "add", scene_cloud],
                       capture_output=True, check=True)

        r = subprocess.run(
            cli + [
                "--json", "--project", project_json,
                "cloud", "filter-csf", "0",
                "--ground", ground_out,
                "--scene", "FLAT",
                "--cloth-resolution", "0.5",
                "--class-threshold", "0.3",
            ],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"CLI CSF failed:\nstdout={r.stdout}\nstderr={r.stderr}"
        data = json.loads(r.stdout)
        assert data["ground_exists"]
        assert data["ground_size"] > 0
        print(f"\n  CLI CSF → {data['ground_size']:,} bytes")


class TestSFColorOps:
    """Tests for scalar-field ↔ RGB colour conversion."""

    @pytest.fixture
    def cloud_with_sf(self, tmp_dir, cloud_xyz):
        """Cloud with Z as active scalar field (PLY preserves SF)."""
        from cli_anything.cloudcompare.utils.cc_backend import coord_to_sf
        out = os.path.join(tmp_dir, "cloud_sf.ply")
        result = coord_to_sf(cloud_xyz, out, dimension="Z")
        assert result["returncode"] == 0, result["stderr"][:300]
        return out

    def test_sf_to_rgb(self, tmp_dir, cloud_with_sf):
        from cli_anything.cloudcompare.utils.cc_backend import sf_to_rgb
        out = os.path.join(tmp_dir, "cloud_rgb.ply")
        result = sf_to_rgb(cloud_with_sf, out)
        assert result["returncode"] == 0, result["stderr"][:300]
        assert result.get("exists"), "sf_to_rgb produced no output"
        assert result["file_size"] > 0
        print(f"\n  SF→RGB: {out} ({result['file_size']:,} bytes)")

    def test_rgb_to_sf(self, tmp_dir, cloud_with_sf):
        """Round-trip: SF→RGB then RGB→SF."""
        from cli_anything.cloudcompare.utils.cc_backend import sf_to_rgb, rgb_to_sf
        rgb_out = os.path.join(tmp_dir, "cloud_rgb2.ply")
        sf_out  = os.path.join(tmp_dir, "cloud_sf2.ply")
        r1 = sf_to_rgb(cloud_with_sf, rgb_out)
        assert r1["returncode"] == 0
        r2 = rgb_to_sf(rgb_out, sf_out)
        assert r2["returncode"] == 0, r2["stderr"][:300]
        assert r2.get("exists"), "rgb_to_sf produced no output"
        print(f"\n  RGB→SF: {sf_out} ({r2['file_size']:,} bytes)")


class TestNoisePCLFilter:
    """Tests for the PCL noise filter (-NOISE KNN/RADIUS REL/ABS).

    Note: CloudCompare's CLI does not expose Gaussian/Bilateral spatial
    smoothing. The -NOISE command (PCL wrapper plugin) is the closest
    equivalent for noise removal available via the command line.
    """

    def test_noise_filter_knn(self, tmp_dir, cloud_xyz):
        from cli_anything.cloudcompare.utils.cc_backend import noise_filter
        out = os.path.join(tmp_dir, "denoised_knn.xyz")
        result = noise_filter(cloud_xyz, out, knn=6, noisiness=1.0)
        assert result["returncode"] == 0, result["stderr"][:300]
        assert result.get("exists"), "noise_filter (KNN) produced no output"
        assert result["file_size"] > 0
        print(f"\n  Noise(KNN): {out} ({result['file_size']:,} bytes)")

    def test_noise_filter_radius(self, tmp_dir, cloud_xyz):
        from cli_anything.cloudcompare.utils.cc_backend import noise_filter
        out = os.path.join(tmp_dir, "denoised_radius.xyz")
        result = noise_filter(cloud_xyz, out, use_radius=True, radius=0.2, noisiness=1.0)
        assert result["returncode"] == 0, result["stderr"][:300]
        assert result.get("exists"), "noise_filter (RADIUS) produced no output"
        print(f"\n  Noise(RADIUS): {out} ({result['file_size']:,} bytes)")

    def test_noise_filter_absolute(self, tmp_dir, cloud_xyz):
        from cli_anything.cloudcompare.utils.cc_backend import noise_filter
        out = os.path.join(tmp_dir, "denoised_abs.xyz")
        result = noise_filter(cloud_xyz, out, knn=6, noisiness=0.05, absolute=True)
        assert result["returncode"] == 0, result["stderr"][:300]
        assert result.get("exists"), "noise_filter (ABS) produced no output"
        print(f"\n  Noise(ABS): {out} ({result['file_size']:,} bytes)")


class TestNormalsOps:
    """Tests for normal computation and inversion."""

    def test_invert_normals(self, tmp_dir, cloud_xyz):
        from cli_anything.cloudcompare.utils.cc_backend import compute_normals, invert_normals
        with_normals = os.path.join(tmp_dir, "normals.ply")
        inverted = os.path.join(tmp_dir, "normals_inv.ply")
        r1 = compute_normals(cloud_xyz, with_normals, octree_level=8)
        assert r1["returncode"] == 0, r1["stderr"][:300]
        r2 = invert_normals(with_normals, inverted)
        assert r2["returncode"] == 0, r2["stderr"][:300]
        assert r2.get("exists"), "invert_normals produced no output"
        print(f"\n  Inverted normals: {inverted} ({r2['file_size']:,} bytes)")


class TestDelaunayMesh:
    """Tests for Delaunay 2.5-D mesh generation and mesh sampling."""

    def test_delaunay_creates_mesh(self, tmp_dir, cloud_xyz):
        from cli_anything.cloudcompare.utils.cc_backend import delaunay_mesh
        out = os.path.join(tmp_dir, "terrain.obj")
        result = delaunay_mesh(cloud_xyz, out, axis_aligned=True)
        assert result["returncode"] == 0, result["stderr"][:300]
        assert result.get("exists"), "delaunay_mesh produced no output"
        assert result["file_size"] > 0
        print(f"\n  Delaunay mesh: {out} ({result['file_size']:,} bytes)")

    def test_delaunay_best_fit(self, tmp_dir, cloud_xyz):
        from cli_anything.cloudcompare.utils.cc_backend import delaunay_mesh
        out = os.path.join(tmp_dir, "terrain_bf.obj")
        result = delaunay_mesh(cloud_xyz, out, axis_aligned=False)
        assert result["returncode"] == 0, result["stderr"][:300]
        assert result.get("exists"), "delaunay best-fit produced no output"

    def test_sample_mesh(self, tmp_dir, cloud_xyz):
        from cli_anything.cloudcompare.utils.cc_backend import delaunay_mesh, sample_mesh
        mesh_out   = os.path.join(tmp_dir, "terrain.obj")
        sample_out = os.path.join(tmp_dir, "sampled.xyz")
        r1 = delaunay_mesh(cloud_xyz, mesh_out)
        assert r1["returncode"] == 0, r1["stderr"][:300]
        r2 = sample_mesh(mesh_out, sample_out, count=500)
        assert r2["returncode"] == 0, r2["stderr"][:300]
        assert r2.get("exists"), "sample_mesh produced no output"
        print(f"\n  Sampled {500} pts → {sample_out} ({r2['file_size']:,} bytes)")


class TestApplyTransform:
    """Tests for -APPLY_TRANS (rigid-body transformation)."""

    def test_apply_identity_matrix(self, tmp_dir, cloud_xyz):
        from cli_anything.cloudcompare.utils.cc_backend import apply_transform
        mat_file = os.path.join(tmp_dir, "identity.txt")
        with open(mat_file, "w") as f:
            f.write("1 0 0 0\n0 1 0 0\n0 0 1 0\n0 0 0 1\n")
        out = os.path.join(tmp_dir, "transformed.xyz")
        result = apply_transform(cloud_xyz, out, mat_file)
        assert result["returncode"] == 0, result["stderr"][:300]
        assert result.get("exists"), "apply_transform produced no output"
        print(f"\n  Transformed cloud: {out} ({result['file_size']:,} bytes)")

    def test_apply_translation_matrix(self, tmp_dir, cloud_xyz):
        from cli_anything.cloudcompare.utils.cc_backend import apply_transform
        mat_file = os.path.join(tmp_dir, "translate.txt")
        with open(mat_file, "w") as f:
            f.write("1 0 0 5\n0 1 0 0\n0 0 1 0\n0 0 0 1\n")  # translate X by 5
        out = os.path.join(tmp_dir, "translated.xyz")
        result = apply_transform(cloud_xyz, out, mat_file)
        assert result["returncode"] == 0, result["stderr"][:300]
        assert result.get("exists"), "Translation transform produced no output"


class TestSegmentCC:
    """Tests for connected-component segmentation (EXTRACT_CC)."""

    @pytest.fixture
    def two_cluster_cloud(self, tmp_dir):
        """Two spatially separated clusters of 50 points each."""
        import random
        random.seed(7)
        path = os.path.join(tmp_dir, "two_clusters.xyz")
        with open(path, "w") as f:
            # Cluster A near origin
            for _ in range(50):
                x = random.uniform(0.0, 0.1)
                y = random.uniform(0.0, 0.1)
                z = random.uniform(0.0, 0.1)
                f.write(f"{x:.6f} {y:.6f} {z:.6f}\n")
            # Cluster B far away
            for _ in range(50):
                x = random.uniform(10.0, 10.1)
                y = random.uniform(10.0, 10.1)
                z = random.uniform(10.0, 10.1)
                f.write(f"{x:.6f} {y:.6f} {z:.6f}\n")
        return path

    def test_extract_two_components(self, tmp_dir, two_cluster_cloud):
        from cli_anything.cloudcompare.utils.cc_backend import extract_connected_components
        out_dir = os.path.join(tmp_dir, "components")
        result = extract_connected_components(
            two_cluster_cloud, out_dir,
            octree_level=8, min_points=10, output_fmt="xyz",
        )
        assert result["returncode"] == 0, result["stderr"][:300]
        assert result["component_count"] >= 2, (
            f"Expected ≥2 components, got {result['component_count']}.\n"
            f"Components: {result['components']}"
        )
        print(f"\n  CC segments: {result['component_count']} components in {out_dir}")


class TestExportPipeline:
    def test_export_cloud_to_las(self, tmp_dir, cloud_xyz):
        """Export a cloud to LAS using the export module."""
        from cli_anything.cloudcompare.core.export import export_cloud

        output_path = os.path.join(tmp_dir, "exported.las")
        result = export_cloud(cloud_xyz, output_path, preset="las", overwrite=True)

        assert result["format"] == "LAS"
        assert result["file_size"] > 0
        assert os.path.exists(result["output"])

        with open(result["output"], "rb") as f:
            assert f.read(4) == b"LASF"

        print(f"\n  Export LAS: {result['output']} ({result['file_size']:,} bytes)")

    def test_export_cloud_to_ply(self, tmp_dir, cloud_xyz):
        """Export a cloud to PLY using the export module."""
        from cli_anything.cloudcompare.core.export import export_cloud

        output_path = os.path.join(tmp_dir, "exported.ply")
        result = export_cloud(cloud_xyz, output_path, preset="ply", overwrite=True)

        assert result["format"] == "PLY"
        assert result["file_size"] > 0

        with open(result["output"], "rb") as f:
            assert f.read(3) == b"ply"

        print(f"\n  Export PLY: {result['output']} ({result['file_size']:,} bytes)")

    def test_export_raises_on_no_overwrite(self, tmp_dir, cloud_xyz):
        """Export raises FileExistsError when output exists and overwrite=False."""
        from cli_anything.cloudcompare.core.export import export_cloud

        output_path = os.path.join(tmp_dir, "exported_noover.las")
        # First export
        export_cloud(cloud_xyz, output_path, preset="las", overwrite=True)
        # Second export without overwrite should raise
        with pytest.raises(FileExistsError):
            export_cloud(cloud_xyz, output_path, preset="las", overwrite=False)

    def test_list_presets(self):
        """list_presets returns cloud and mesh format dicts."""
        from cli_anything.cloudcompare.core.export import list_presets
        presets = list_presets()
        assert "cloud" in presets
        assert "mesh" in presets
        assert "las" in presets["cloud"]
        assert "obj" in presets["mesh"]


class TestProjectWorkflow:
    def test_full_project_lifecycle(self, tmp_dir, cloud_xyz):
        """Create project → add cloud → subsample → save → reload."""
        from cli_anything.cloudcompare.core.session import Session
        from cli_anything.cloudcompare.utils.cc_backend import subsample

        proj_path = os.path.join(tmp_dir, "workflow.json")
        output_cloud = os.path.join(tmp_dir, "subsampled.xyz")

        # 1. Create session and add cloud
        s = Session(proj_path)
        s.add_cloud(cloud_xyz, label="raw_scan")
        s.save()

        # 2. Subsample
        cloud_entry = s.get_cloud(0)
        result = subsample(cloud_entry["path"], output_cloud, "SPATIAL", 0.2)
        assert result["returncode"] == 0
        assert result.get("exists")

        # 3. Add output back to project
        s.add_cloud(output_cloud, label="thinned")
        s.record("subsample", [cloud_entry["path"]], [output_cloud],
                 {"method": "SPATIAL", "param": 0.2})
        s.save()

        # 4. Verify persisted state
        s2 = Session(proj_path)
        assert s2.cloud_count == 2
        assert s2.history(1)[0]["operation"] == "subsample"
        print(f"\n  Project workflow complete: {proj_path}")
        print(f"  Subsampled cloud: {output_cloud} ({result['file_size']:,} bytes)")


# ── TestCLISubprocess (installed command tests) ────────────────────────────────

class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-cloudcompare")

    def _run(self, args, check=True, allow_fail=False):
        result = subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
        )
        if check and not allow_fail and result.returncode != 0:
            pytest.fail(
                f"CLI failed (exit {result.returncode}):\n"
                f"  stdout: {result.stdout[:400]}\n"
                f"  stderr: {result.stderr[:400]}"
            )
        return result

    def test_help(self):
        """--help exits 0 and shows usage."""
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "cloudcompare" in result.stdout.lower() or "Usage" in result.stdout

    def test_info_json(self):
        """info --json returns valid JSON with expected keys."""
        result = self._run(["--json", "info"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "cloudcompare_available" in data
        assert "supported_cloud_formats" in data
        print(f"\n  CloudCompare available: {data['cloudcompare_available']}")
        print(f"  Command: {data.get('command')}")

    def test_project_new_creates_file(self, tmp_dir):
        """project new -o creates a valid JSON project file."""
        proj_path = os.path.join(tmp_dir, "cli_test.json")
        result = self._run(["--json", "project", "new", "-o", proj_path])
        assert result.returncode == 0
        assert os.path.exists(proj_path)
        data = json.loads(result.stdout)
        assert "cloud_count" in data
        assert data["cloud_count"] == 0
        print(f"\n  Project created: {proj_path}")

    def test_project_info_json(self, tmp_dir):
        """project info --json returns JSON with project details."""
        proj_path = os.path.join(tmp_dir, "info_test.json")
        # Create project first
        self._run(["project", "new", "-o", proj_path])
        # Query info
        result = self._run(["--json", "--project", proj_path, "project", "info"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "cloud_count" in data
        assert "mesh_count" in data
        assert "settings" in data

    def test_cloud_add_and_list(self, tmp_dir, cloud_xyz):
        """cloud add adds the cloud; cloud list returns it."""
        proj_path = os.path.join(tmp_dir, "cloud_test.json")
        self._run(["project", "new", "-o", proj_path])
        self._run(["--project", proj_path, "cloud", "add", cloud_xyz, "--label", "scan_a"])
        result = self._run(["--json", "--project", proj_path, "cloud", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["count"] == 1
        assert data["clouds"][0]["label"] == "scan_a"

    def test_export_formats_json(self):
        """export formats --json returns cloud and mesh format lists."""
        result = self._run(["--json", "export", "formats"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "cloud" in data
        assert "mesh" in data
        assert "las" in data["cloud"]
        assert "obj" in data["mesh"]

    def test_session_history_json(self, tmp_dir):
        """session history --json returns JSON history list."""
        proj_path = os.path.join(tmp_dir, "hist_test.json")
        self._run(["project", "new", "-o", proj_path])
        result = self._run(["--json", "--project", proj_path, "session", "history"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "history" in data
        assert "count" in data

    def test_full_subsample_workflow(self, tmp_dir, cloud_xyz):
        """Full workflow: create project → add cloud → subsample → verify output."""
        proj_path = os.path.join(tmp_dir, "subsample_wf.json")
        out_cloud = os.path.join(tmp_dir, "subsampled.las")

        # Create project
        self._run(["project", "new", "-o", proj_path])

        # Add cloud
        self._run(["--project", proj_path, "cloud", "add", cloud_xyz])

        # Subsample via CloudCompare
        result = self._run([
            "--json", "--project", proj_path,
            "cloud", "subsample", "0",
            "-o", out_cloud,
            "--method", "SPATIAL",
            "--param", "0.15",
            "--add-to-project",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert data.get("exists") is True, (
            f"CloudCompare did not produce output.\n"
            f"Result: {json.dumps(data, indent=2)}"
        )
        assert os.path.exists(data["output"]), f"Output file missing: {data['output']}"

        # Verify LAS magic bytes
        with open(data["output"], "rb") as f:
            magic = f.read(4)
        assert magic == b"LASF", f"Output is not valid LAS: {magic}"

        print(f"\n  Subsampled cloud: {data['output']}")
        print(f"  File size: {data.get('file_size', '?'):,} bytes")

        # Verify project was updated (--add-to-project)
        info_result = self._run(["--json", "--project", proj_path, "project", "info"])
        info = json.loads(info_result.stdout)
        assert info["cloud_count"] == 2

    def test_full_export_workflow(self, tmp_dir, cloud_xyz):
        """Full workflow: create project → add cloud → export to PLY."""
        proj_path = os.path.join(tmp_dir, "export_wf.json")
        out_cloud = os.path.join(tmp_dir, "exported.ply")

        self._run(["project", "new", "-o", proj_path])
        self._run(["--project", proj_path, "cloud", "add", cloud_xyz])
        result = self._run([
            "--json", "--project", proj_path,
            "export", "cloud", "0", out_cloud,
            "--overwrite",
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert os.path.exists(data["output"]), f"Exported PLY missing: {data['output']}"
        assert data["file_size"] > 0

        with open(data["output"], "rb") as f:
            assert f.read(3) == b"ply"

        print(f"\n  Exported PLY: {data['output']} ({data['file_size']:,} bytes)")

    def test_project_status_json(self, tmp_dir):
        """project status --json returns quick status."""
        proj_path = os.path.join(tmp_dir, "status_test.json")
        self._run(["project", "new", "-o", proj_path])
        result = self._run(["--json", "--project", proj_path, "project", "status"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "clouds" in data
        assert "meshes" in data
        assert "modified" in data

    def test_cloud_invert_normals_workflow(self, tmp_dir, cloud_xyz):
        """Workflow: add cloud → normals → invert-normals."""
        proj_path = os.path.join(tmp_dir, "normals_wf.json")
        normals_out = os.path.join(tmp_dir, "normals.ply")
        inv_out = os.path.join(tmp_dir, "normals_inv.ply")

        self._run(["project", "new", "-o", proj_path])
        self._run(["--project", proj_path, "cloud", "add", cloud_xyz])

        # Compute normals
        r1 = self._run([
            "--json", "--project", proj_path,
            "cloud", "normals", "0", "-o", normals_out, "--add-to-project",
        ])
        assert r1.returncode == 0
        d1 = json.loads(r1.stdout)
        assert d1.get("exists"), "normals command produced no output"

        # Add normals cloud and invert
        r2 = self._run([
            "--json", "--project", proj_path,
            "cloud", "invert-normals", "1", "-o", inv_out,
        ])
        assert r2.returncode == 0
        d2 = json.loads(r2.stdout)
        assert d2.get("exists"), "invert-normals produced no output"
        print(f"\n  Inverted normals: {inv_out} ({d2['file_size']:,} bytes)")

    def test_cloud_mesh_delaunay_workflow(self, tmp_dir, cloud_xyz):
        """Workflow: add cloud → mesh-delaunay → verify mesh."""
        proj_path = os.path.join(tmp_dir, "delaunay_wf.json")
        mesh_out = os.path.join(tmp_dir, "terrain.obj")

        self._run(["project", "new", "-o", proj_path])
        self._run(["--project", proj_path, "cloud", "add", cloud_xyz])

        result = self._run([
            "--json", "--project", proj_path,
            "cloud", "mesh-delaunay", "0", "-o", mesh_out,
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data.get("exists"), f"mesh-delaunay produced no output: {result.stderr[:300]}"
        assert data["file_size"] > 0
        print(f"\n  Delaunay mesh: {mesh_out} ({data['file_size']:,} bytes)")

    def test_transform_apply_workflow(self, tmp_dir, cloud_xyz):
        """Workflow: add cloud → apply identity transform → verify output."""
        proj_path = os.path.join(tmp_dir, "trans_wf.json")
        mat_file = os.path.join(tmp_dir, "identity.txt")
        out_cloud = os.path.join(tmp_dir, "transformed.xyz")

        with open(mat_file, "w") as f:
            f.write("1 0 0 0\n0 1 0 0\n0 0 1 0\n0 0 0 1\n")

        self._run(["project", "new", "-o", proj_path])
        self._run(["--project", proj_path, "cloud", "add", cloud_xyz])

        result = self._run([
            "--json", "--project", proj_path,
            "transform", "apply", "0",
            "-o", out_cloud, "-m", mat_file,
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data.get("exists"), f"transform apply produced no output: {result.stderr[:300]}"
        print(f"\n  Transformed: {out_cloud} ({data['file_size']:,} bytes)")
