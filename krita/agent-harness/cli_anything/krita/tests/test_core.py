"""Unit tests for cli-anything-krita core modules.

All tests use synthetic data — no external dependencies required.
"""

import copy
import json
import os
import tempfile
import zipfile

import pytest

from cli_anything.krita.core.project import (
    create_project,
    open_project,
    save_project,
    project_info,
    add_layer,
    remove_layer,
    list_layers,
    set_layer_property,
    add_filter,
    set_canvas,
)
from cli_anything.krita.core.session import Session
from cli_anything.krita.core.export import (
    list_presets,
    get_supported_formats,
    EXPORT_PRESETS,
    build_kra_from_project,
)


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def sample_project():
    return create_project(name="Test", width=800, height=600)


# ===========================================================================
# project.py tests
# ===========================================================================

class TestProject:
    def test_create_project_defaults(self):
        proj = create_project(name="Default")
        assert proj["name"] == "Default"
        assert proj["canvas"]["width"] == 1920
        assert proj["canvas"]["height"] == 1080
        assert proj["canvas"]["colorspace"] == "RGBA"
        assert proj["canvas"]["depth"] == "U8"
        assert proj["canvas"]["resolution"] == 300
        assert len(proj["layers"]) == 1
        assert proj["layers"][0]["name"] == "Background"

    def test_create_project_custom(self):
        proj = create_project(
            name="Custom", width=4096, height=4096,
            colorspace="CMYKA", depth="F32", resolution=600,
        )
        assert proj["canvas"]["width"] == 4096
        assert proj["canvas"]["height"] == 4096
        assert proj["canvas"]["colorspace"] == "CMYKA"
        assert proj["canvas"]["depth"] == "F32"
        assert proj["canvas"]["resolution"] == 600

    def test_save_and_open_project(self, tmp_dir, sample_project):
        path = os.path.join(tmp_dir, "proj.json")
        save_project(sample_project, path)
        assert os.path.exists(path)
        loaded = open_project(path)
        assert loaded["name"] == "Test"
        assert loaded["canvas"]["width"] == 800

    def test_project_info(self, sample_project):
        info = project_info(sample_project)
        assert "name" in info
        assert "canvas" in info or "layer_count" in info

    def test_add_layer_paintlayer(self, sample_project):
        add_layer(sample_project, "Sketch", layer_type="paintlayer")
        layers = list_layers(sample_project)
        names = [l["name"] for l in layers]
        assert "Sketch" in names

    def test_add_layer_grouplayer(self, sample_project):
        add_layer(sample_project, "Group1", layer_type="grouplayer")
        layers = list_layers(sample_project)
        found = [l for l in layers if l["name"] == "Group1"]
        assert len(found) == 1
        assert found[0]["type"] == "grouplayer"

    def test_add_layer_all_types(self, sample_project):
        types = ["paintlayer", "grouplayer", "vectorlayer", "filterlayer",
                 "filllayer", "clonelayer", "filelayer"]
        for lt in types:
            add_layer(sample_project, f"Layer_{lt}", layer_type=lt)
        layers = list_layers(sample_project)
        assert len(layers) == 1 + len(types)  # Background + added

    def test_remove_layer(self, sample_project):
        add_layer(sample_project, "ToRemove")
        remove_layer(sample_project, "ToRemove")
        names = [l["name"] for l in list_layers(sample_project)]
        assert "ToRemove" not in names

    def test_remove_layer_not_found(self, sample_project):
        with pytest.raises((ValueError, KeyError, RuntimeError)):
            remove_layer(sample_project, "NonExistent")

    def test_list_layers(self, sample_project):
        add_layer(sample_project, "A")
        add_layer(sample_project, "B")
        layers = list_layers(sample_project)
        assert len(layers) == 3  # Background + A + B
        assert all("name" in l for l in layers)

    def test_set_layer_property_opacity(self, sample_project):
        set_layer_property(sample_project, "Background", "opacity", 128)
        layers = list_layers(sample_project)
        bg = [l for l in layers if l["name"] == "Background"][0]
        assert bg["opacity"] == 128

    def test_set_layer_property_visible(self, sample_project):
        set_layer_property(sample_project, "Background", "visible", False)
        layers = list_layers(sample_project)
        bg = [l for l in layers if l["name"] == "Background"][0]
        assert bg["visible"] is False

    def test_set_layer_property_blending(self, sample_project):
        set_layer_property(sample_project, "Background", "blending_mode", "multiply")
        layers = list_layers(sample_project)
        bg = [l for l in layers if l["name"] == "Background"][0]
        assert bg["blending_mode"] == "multiply"

    def test_add_filter(self, sample_project):
        add_filter(sample_project, "Background", "blur")
        layers = list_layers(sample_project)
        bg = [l for l in layers if l["name"] == "Background"][0]
        assert len(bg["filters"]) == 1
        assert bg["filters"][0]["name"] == "blur"

    def test_add_filter_with_config(self, sample_project):
        add_filter(sample_project, "Background", "blur", {"radius": 5.0})
        layers = list_layers(sample_project)
        bg = [l for l in layers if l["name"] == "Background"][0]
        assert bg["filters"][0]["config"]["radius"] == 5.0

    def test_set_canvas(self, sample_project):
        set_canvas(sample_project, width=3840, height=2160, resolution=150)
        assert sample_project["canvas"]["width"] == 3840
        assert sample_project["canvas"]["height"] == 2160
        assert sample_project["canvas"]["resolution"] == 150

    def test_set_canvas_partial(self, sample_project):
        original_height = sample_project["canvas"]["height"]
        set_canvas(sample_project, width=1024)
        assert sample_project["canvas"]["width"] == 1024
        assert sample_project["canvas"]["height"] == original_height


# ===========================================================================
# session.py tests
# ===========================================================================

class TestSession:
    def test_session_snapshot(self, sample_project):
        sess = Session()
        sess.snapshot(sample_project, "initial")
        assert len(sess.history()) == 1

    def test_session_undo(self, sample_project):
        sess = Session()
        sess.snapshot(sample_project, "state1")
        modified = copy.deepcopy(sample_project)
        modified["name"] = "Modified"
        sess.snapshot(modified, "state2")
        restored = sess.undo()
        assert restored is not None
        assert restored["name"] == "Test"

    def test_session_redo(self, sample_project):
        sess = Session()
        sess.snapshot(sample_project, "state1")
        modified = copy.deepcopy(sample_project)
        modified["name"] = "Modified"
        sess.snapshot(modified, "state2")
        sess.undo()
        restored = sess.redo()
        assert restored is not None
        assert restored["name"] == "Modified"

    def test_session_undo_at_start(self, sample_project):
        sess = Session()
        sess.snapshot(sample_project, "only")
        result = sess.undo()
        assert result is None

    def test_session_redo_at_end(self, sample_project):
        sess = Session()
        sess.snapshot(sample_project, "only")
        result = sess.redo()
        assert result is None

    def test_session_branch_discards_redo(self, sample_project):
        sess = Session()
        sess.snapshot(sample_project, "s1")
        m1 = copy.deepcopy(sample_project)
        m1["name"] = "M1"
        sess.snapshot(m1, "s2")
        m2 = copy.deepcopy(sample_project)
        m2["name"] = "M2"
        sess.snapshot(m2, "s3")
        sess.undo()  # back to s2
        sess.undo()  # back to s1
        branch = copy.deepcopy(sample_project)
        branch["name"] = "Branch"
        sess.snapshot(branch, "branch")
        assert len(sess.history()) == 2  # s1 + branch
        assert sess.redo() is None

    def test_session_history(self, sample_project):
        sess = Session()
        sess.snapshot(sample_project, "a")
        sess.snapshot(sample_project, "b")
        sess.snapshot(sample_project, "c")
        hist = sess.history()
        assert len(hist) == 3

    def test_session_save_load(self, tmp_dir, sample_project):
        sess = Session()
        sess.snapshot(sample_project, "saved")
        path = os.path.join(tmp_dir, "session.json")
        sess.save(path)
        assert os.path.exists(path)
        sess2 = Session()
        sess2.load(path)
        assert len(sess2.history()) == 1

    def test_session_clear(self, sample_project):
        sess = Session()
        sess.snapshot(sample_project, "a")
        sess.snapshot(sample_project, "b")
        sess.clear()
        assert len(sess.history()) == 0

    def test_session_can_undo_redo(self, sample_project):
        sess = Session()
        assert sess.can_undo() is False
        assert sess.can_redo() is False
        sess.snapshot(sample_project, "s1")
        assert sess.can_undo() is False  # only one state
        m = copy.deepcopy(sample_project)
        m["name"] = "m"
        sess.snapshot(m, "s2")
        assert sess.can_undo() is True
        assert sess.can_redo() is False
        sess.undo()
        assert sess.can_redo() is True


# ===========================================================================
# export.py tests
# ===========================================================================

class TestExport:
    def test_list_presets(self):
        presets = list_presets()
        assert len(presets) > 0
        assert all("name" in p for p in presets)

    def test_get_supported_formats(self):
        formats = get_supported_formats()
        assert "png" in formats
        assert "jpg" in formats

    def test_export_presets_keys(self):
        for name, preset in EXPORT_PRESETS.items():
            assert "extension" in preset or "format" in preset, f"Preset {name} missing format key"
            assert "description" in preset, f"Preset {name} missing 'description'"

    def test_build_kra_from_project(self, tmp_dir, sample_project):
        kra_path = os.path.join(tmp_dir, "test.kra")
        result = build_kra_from_project(sample_project, kra_path)
        assert os.path.exists(result)
        assert os.path.getsize(result) > 0

    def test_kra_has_mimetype(self, tmp_dir, sample_project):
        kra_path = os.path.join(tmp_dir, "test.kra")
        build_kra_from_project(sample_project, kra_path)
        with zipfile.ZipFile(kra_path, "r") as zf:
            assert "mimetype" in zf.namelist()
            assert zf.read("mimetype") == b"application/x-kra"

    def test_kra_has_maindoc(self, tmp_dir, sample_project):
        kra_path = os.path.join(tmp_dir, "test.kra")
        build_kra_from_project(sample_project, kra_path)
        with zipfile.ZipFile(kra_path, "r") as zf:
            assert "maindoc.xml" in zf.namelist()
            content = zf.read("maindoc.xml").decode("utf-8")
            assert "krita" in content.lower() or "DOC" in content

    def test_kra_has_documentinfo(self, tmp_dir, sample_project):
        kra_path = os.path.join(tmp_dir, "test.kra")
        build_kra_from_project(sample_project, kra_path)
        with zipfile.ZipFile(kra_path, "r") as zf:
            assert "documentinfo.xml" in zf.namelist()


# ===========================================================================
# krita_backend.py tests
# ===========================================================================

class TestKritaBackend:
    def test_find_krita(self):
        from cli_anything.krita.utils.krita_backend import find_krita
        path = find_krita()
        assert path is not None
        assert os.path.exists(path)

    def test_get_version(self):
        from cli_anything.krita.utils.krita_backend import get_version
        version = get_version()
        assert isinstance(version, str)
        assert len(version) > 0
