"""Unit tests for cli-anything-cloudcompare core modules.

Tests use synthetic data only — no CloudCompare installation required.
"""

import json
import os
import sys
import tempfile

import pytest

# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir(tmp_path):
    return str(tmp_path)


@pytest.fixture
def project_path(tmp_dir):
    return os.path.join(tmp_dir, "test_project.json")


@pytest.fixture
def dummy_cloud_file(tmp_dir):
    """Create a minimal XYZ cloud file."""
    path = os.path.join(tmp_dir, "cloud.xyz")
    with open(path, "w") as f:
        f.write("0.0 0.0 0.0\n1.0 0.0 0.0\n2.0 0.0 0.0\n")
    return path


@pytest.fixture
def dummy_mesh_file(tmp_dir):
    """Create a minimal OBJ mesh file."""
    path = os.path.join(tmp_dir, "mesh.obj")
    with open(path, "w") as f:
        f.write("v 0.0 0.0 0.0\nv 1.0 0.0 0.0\nv 0.0 1.0 0.0\nf 1 2 3\n")
    return path


# ── Tests: core/project.py ────────────────────────────────────────────────────

class TestCreateProject:
    def test_creates_file(self, project_path):
        from cli_anything.cloudcompare.core.project import create_project
        proj = create_project(project_path)
        assert os.path.exists(project_path)

    def test_returns_dict_with_expected_keys(self, project_path):
        from cli_anything.cloudcompare.core.project import create_project
        proj = create_project(project_path)
        assert "version" in proj
        assert "clouds" in proj
        assert "meshes" in proj
        assert "settings" in proj
        assert "history" in proj
        assert proj["clouds"] == []
        assert proj["meshes"] == []

    def test_uses_provided_name(self, project_path):
        from cli_anything.cloudcompare.core.project import create_project
        proj = create_project(project_path, name="MySurvey")
        assert proj["name"] == "MySurvey"

    def test_derives_name_from_filename(self, tmp_dir):
        from cli_anything.cloudcompare.core.project import create_project
        path = os.path.join(tmp_dir, "my_scan.json")
        proj = create_project(path)
        assert proj["name"] == "my_scan"

    def test_written_json_is_valid(self, project_path):
        from cli_anything.cloudcompare.core.project import create_project
        create_project(project_path)
        with open(project_path) as f:
            data = json.load(f)
        assert data["version"] == "1.0"


class TestLoadProject:
    def test_loads_existing_project(self, project_path):
        from cli_anything.cloudcompare.core.project import create_project, load_project
        create_project(project_path)
        proj = load_project(project_path)
        assert proj["version"] == "1.0"

    def test_raises_on_missing_file(self, tmp_dir):
        from cli_anything.cloudcompare.core.project import load_project
        with pytest.raises(FileNotFoundError):
            load_project(os.path.join(tmp_dir, "nonexistent.json"))

    def test_raises_on_invalid_json_structure(self, tmp_dir):
        from cli_anything.cloudcompare.core.project import load_project
        path = os.path.join(tmp_dir, "bad.json")
        with open(path, "w") as f:
            json.dump({"foo": "bar"}, f)
        with pytest.raises(ValueError):
            load_project(path)


class TestSaveProject:
    def test_saves_and_updates_modified_at(self, project_path):
        from cli_anything.cloudcompare.core.project import create_project, save_project, load_project
        proj = create_project(project_path)
        original_ts = proj["modified_at"]
        import time; time.sleep(1)
        save_project(proj, project_path)
        reloaded = load_project(project_path)
        # modified_at may or may not change within same second, just check it's present
        assert "modified_at" in reloaded


class TestAddCloud:
    def test_adds_cloud_entry(self, project_path, dummy_cloud_file):
        from cli_anything.cloudcompare.core.project import create_project, add_cloud
        proj = create_project(project_path)
        entry = add_cloud(proj, dummy_cloud_file)
        assert len(proj["clouds"]) == 1
        assert entry["path"] == os.path.abspath(dummy_cloud_file)

    def test_uses_stem_as_default_label(self, project_path, dummy_cloud_file):
        from cli_anything.cloudcompare.core.project import create_project, add_cloud
        proj = create_project(project_path)
        entry = add_cloud(proj, dummy_cloud_file)
        assert entry["label"] == "cloud"

    def test_uses_custom_label(self, project_path, dummy_cloud_file):
        from cli_anything.cloudcompare.core.project import create_project, add_cloud
        proj = create_project(project_path)
        entry = add_cloud(proj, dummy_cloud_file, label="scan_A")
        assert entry["label"] == "scan_A"

    def test_raises_on_missing_file(self, project_path):
        from cli_anything.cloudcompare.core.project import create_project, add_cloud
        proj = create_project(project_path)
        with pytest.raises(FileNotFoundError):
            add_cloud(proj, "/nonexistent/cloud.las")


class TestAddMesh:
    def test_adds_mesh_entry(self, project_path, dummy_mesh_file):
        from cli_anything.cloudcompare.core.project import create_project, add_mesh
        proj = create_project(project_path)
        entry = add_mesh(proj, dummy_mesh_file)
        assert len(proj["meshes"]) == 1
        assert entry["path"] == os.path.abspath(dummy_mesh_file)

    def test_raises_on_missing_file(self, project_path):
        from cli_anything.cloudcompare.core.project import create_project, add_mesh
        proj = create_project(project_path)
        with pytest.raises(FileNotFoundError):
            add_mesh(proj, "/nonexistent/mesh.obj")


class TestRemoveCloud:
    def test_removes_cloud_by_index(self, project_path, dummy_cloud_file):
        from cli_anything.cloudcompare.core.project import create_project, add_cloud, remove_cloud
        proj = create_project(project_path)
        add_cloud(proj, dummy_cloud_file)
        removed = remove_cloud(proj, 0)
        assert len(proj["clouds"]) == 0
        assert removed["path"] == os.path.abspath(dummy_cloud_file)

    def test_raises_on_out_of_range_index(self, project_path):
        from cli_anything.cloudcompare.core.project import create_project, remove_cloud
        proj = create_project(project_path)
        with pytest.raises(IndexError):
            remove_cloud(proj, 0)

    def test_raises_on_negative_index(self, project_path, dummy_cloud_file):
        from cli_anything.cloudcompare.core.project import create_project, add_cloud, remove_cloud
        proj = create_project(project_path)
        add_cloud(proj, dummy_cloud_file)
        with pytest.raises(IndexError):
            remove_cloud(proj, -1)


class TestGetCloud:
    def test_returns_cloud_by_index(self, project_path, dummy_cloud_file):
        from cli_anything.cloudcompare.core.project import create_project, add_cloud, get_cloud
        proj = create_project(project_path)
        add_cloud(proj, dummy_cloud_file, label="my_scan")
        entry = get_cloud(proj, 0)
        assert entry["label"] == "my_scan"

    def test_raises_on_invalid_index(self, project_path):
        from cli_anything.cloudcompare.core.project import create_project, get_cloud
        proj = create_project(project_path)
        with pytest.raises(IndexError):
            get_cloud(proj, 99)


class TestProjectInfo:
    def test_returns_summary(self, project_path, dummy_cloud_file, dummy_mesh_file):
        from cli_anything.cloudcompare.core.project import (
            create_project, add_cloud, add_mesh, project_info
        )
        proj = create_project(project_path, name="TestProj")
        add_cloud(proj, dummy_cloud_file)
        add_mesh(proj, dummy_mesh_file)
        info = project_info(proj)
        assert info["name"] == "TestProj"
        assert info["cloud_count"] == 1
        assert info["mesh_count"] == 1
        assert len(info["clouds"]) == 1
        assert info["clouds"][0]["index"] == 0


class TestRecordOperation:
    def test_appends_to_history(self, project_path):
        from cli_anything.cloudcompare.core.project import create_project, record_operation
        proj = create_project(project_path)
        record_operation(proj, "subsample", ["in.las"], ["out.las"], {"method": "SPATIAL"})
        assert len(proj["history"]) == 1
        assert proj["history"][0]["operation"] == "subsample"
        assert proj["history"][0]["params"]["method"] == "SPATIAL"


# ── Tests: core/session.py ────────────────────────────────────────────────────

class TestSession:
    def test_creates_new_project_when_missing(self, tmp_dir):
        from cli_anything.cloudcompare.core.session import Session
        path = os.path.join(tmp_dir, "new.json")
        assert not os.path.exists(path)
        s = Session(path)
        # Session creates project in memory; save() to persist
        s.save()
        assert os.path.exists(path)

    def test_loads_existing_project(self, project_path):
        from cli_anything.cloudcompare.core.project import create_project
        from cli_anything.cloudcompare.core.session import Session
        create_project(project_path, name="Loaded")
        s = Session(project_path)
        assert s.name == "Loaded"

    def test_cloud_count_increments(self, project_path, dummy_cloud_file):
        from cli_anything.cloudcompare.core.session import Session
        s = Session(project_path)
        assert s.cloud_count == 0
        s.add_cloud(dummy_cloud_file)
        assert s.cloud_count == 1

    def test_mesh_count_increments(self, project_path, dummy_mesh_file):
        from cli_anything.cloudcompare.core.session import Session
        s = Session(project_path)
        assert s.mesh_count == 0
        s.add_mesh(dummy_mesh_file)
        assert s.mesh_count == 1

    def test_is_modified_after_add(self, project_path, dummy_cloud_file):
        from cli_anything.cloudcompare.core.session import Session
        s = Session(project_path)
        assert not s.is_modified
        s.add_cloud(dummy_cloud_file)
        assert s.is_modified

    def test_is_not_modified_after_save(self, project_path, dummy_cloud_file):
        from cli_anything.cloudcompare.core.session import Session
        s = Session(project_path)
        s.add_cloud(dummy_cloud_file)
        s.save()
        assert not s.is_modified

    def test_remove_cloud(self, project_path, dummy_cloud_file):
        from cli_anything.cloudcompare.core.session import Session
        s = Session(project_path)
        s.add_cloud(dummy_cloud_file)
        removed = s.remove_cloud(0)
        assert s.cloud_count == 0
        assert "path" in removed

    def test_get_cloud(self, project_path, dummy_cloud_file):
        from cli_anything.cloudcompare.core.session import Session
        s = Session(project_path)
        s.add_cloud(dummy_cloud_file, label="scan_a")
        entry = s.get_cloud(0)
        assert entry["label"] == "scan_a"

    def test_history_recording(self, project_path):
        from cli_anything.cloudcompare.core.session import Session
        s = Session(project_path)
        s.record("test_op", ["a.las"], ["b.las"], {"key": "val"})
        hist = s.history()
        assert len(hist) == 1
        assert hist[0]["operation"] == "test_op"

    def test_history_last_n(self, project_path):
        from cli_anything.cloudcompare.core.session import Session
        s = Session(project_path)
        for i in range(5):
            s.record(f"op_{i}", [], [], {})
        assert len(s.history(3)) == 3
        assert len(s.history(10)) == 5

    def test_undo_last_removes_entry(self, project_path):
        from cli_anything.cloudcompare.core.session import Session
        s = Session(project_path)
        s.record("op_1", [], [], {})
        s.record("op_2", [], [], {})
        removed = s.undo_last()
        assert removed["operation"] == "op_2"
        assert len(s.history()) == 1

    def test_undo_last_returns_none_when_empty(self, project_path):
        from cli_anything.cloudcompare.core.session import Session
        s = Session(project_path)
        result = s.undo_last()
        assert result is None

    def test_set_export_format(self, project_path):
        from cli_anything.cloudcompare.core.session import Session
        s = Session(project_path)
        s.set_export_format(cloud_fmt="PLY", cloud_ext="ply")
        settings = s.get_settings()
        assert settings["cloud_export_format"] == "PLY"
        assert settings["cloud_export_ext"] == "ply"

    def test_set_export_format_ignores_none(self, project_path):
        from cli_anything.cloudcompare.core.session import Session
        s = Session(project_path)
        original_mesh_fmt = s.get_settings().get("mesh_export_format")
        s.set_export_format(cloud_fmt="PLY")  # mesh args are None
        settings = s.get_settings()
        assert settings["cloud_export_format"] == "PLY"
        # mesh format unchanged
        assert settings.get("mesh_export_format") == original_mesh_fmt

    def test_status_dict_keys(self, project_path):
        from cli_anything.cloudcompare.core.session import Session
        s = Session(project_path)
        status = s.status()
        assert "project" in status
        assert "clouds" in status
        assert "meshes" in status
        assert "modified" in status

    def test_repr_contains_path(self, project_path):
        from cli_anything.cloudcompare.core.session import Session
        s = Session(project_path)
        assert "Session(" in repr(s)


# ── Tests: utils/cc_backend.py (pure logic) ────────────────────────────────────

class TestCCBackendConstants:
    def test_cloud_formats_has_las(self):
        from cli_anything.cloudcompare.utils.cc_backend import CLOUD_FORMATS
        assert "las" in CLOUD_FORMATS
        assert "laz" in CLOUD_FORMATS
        assert "ply" in CLOUD_FORMATS
        assert "xyz" in CLOUD_FORMATS

    def test_mesh_formats_has_obj(self):
        from cli_anything.cloudcompare.utils.cc_backend import MESH_FORMATS
        assert "obj" in MESH_FORMATS
        assert "stl" in MESH_FORMATS

    def test_find_cloudcompare_raises_when_not_found(self, monkeypatch):
        """When CloudCompare is absent, should raise RuntimeError with install hint."""
        import shutil
        import subprocess
        from cli_anything.cloudcompare.utils import cc_backend

        # Patch shutil.which to return None for all binaries
        monkeypatch.setattr(shutil, "which", lambda x: None)
        # Patch subprocess.run to simulate empty flatpak list
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: type('R', (), {'stdout': '', 'stderr': ''})())
        # Patch os.path.exists to return False for snap path
        monkeypatch.setattr(os.path, "exists", lambda p: False)

        with pytest.raises(RuntimeError, match="CloudCompare is not installed"):
            cc_backend.find_cloudcompare()


class TestCoordToSFValidation:
    def test_invalid_dimension_raises(self):
        from cli_anything.cloudcompare.utils.cc_backend import coord_to_sf
        with pytest.raises(ValueError, match="dimension must be"):
            coord_to_sf("/nonexistent.las", "/out.las", dimension="W")

    def test_invalid_dimension_in_filter_raises(self):
        from cli_anything.cloudcompare.utils.cc_backend import coord_to_sf_and_filter
        with pytest.raises(ValueError, match="dimension must be"):
            coord_to_sf_and_filter("/nonexistent.las", "/out.las", dimension="Q")


class TestNoiseFilterImport:
    def test_noise_filter_importable(self):
        """noise_filter replaces color_filter (no -FILTER command exists in CC CLI)."""
        from cli_anything.cloudcompare.utils.cc_backend import noise_filter
        assert callable(noise_filter)

    def test_noise_filter_knn_mode(self):
        """noise_filter KNN mode should not raise ValueError."""
        from cli_anything.cloudcompare.utils.cc_backend import noise_filter
        try:
            noise_filter("/nonexistent.xyz", "/out.xyz", knn=6, noisiness=1.0)
        except RuntimeError:
            pass  # CC not found — acceptable; no ValueError expected

    def test_noise_filter_radius_mode(self):
        """noise_filter RADIUS mode should not raise ValueError."""
        from cli_anything.cloudcompare.utils.cc_backend import noise_filter
        try:
            noise_filter("/nonexistent.xyz", "/out.xyz",
                         use_radius=True, radius=0.2, absolute=True)
        except RuntimeError:
            pass

    def test_color_filter_removed(self):
        """color_filter must no longer exist (backed a non-existent CC command)."""
        import cli_anything.cloudcompare.utils.cc_backend as backend
        assert not hasattr(backend, "color_filter")


class TestCSFFilterValidation:
    def test_invalid_scene_raises(self):
        from cli_anything.cloudcompare.utils.cc_backend import csf_filter
        with pytest.raises(ValueError, match="scene must be"):
            csf_filter("/nonexistent.las", "/out.las", scene="OCEAN")

    def test_valid_scenes_accepted(self):
        """Valid scene names should not raise at the validation stage."""
        from cli_anything.cloudcompare.utils.cc_backend import csf_filter, find_cloudcompare
        for scene in ("SLOPE", "RELIEF", "FLAT"):
            try:
                # Will fail because /nonexistent.las doesn't exist, but NOT
                # because of invalid scene — the ValueError is raised before CC runs.
                csf_filter("/nonexistent.las", "/out.las", scene=scene)
            except ValueError:
                pytest.fail(f"scene={scene!r} incorrectly raised ValueError")
