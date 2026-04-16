"""Unit tests for GIMP CLI core modules.

Tests use synthetic data only — no real images or external dependencies.
"""

import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.gimp.core.project import create_project, open_project, save_project, get_project_info, list_profiles
from cli_anything.gimp.core.layers import (
    add_layer, add_from_file, remove_layer, duplicate_layer, move_layer,
    set_layer_property, get_layer, list_layers, BLEND_MODES,
)
from cli_anything.gimp.core.filters import (
    list_available, get_filter_info, validate_params, add_filter,
    remove_filter, set_filter_param, list_filters, FILTER_REGISTRY,
)
from cli_anything.gimp.core.canvas import (
    resize_canvas, scale_canvas, crop_canvas, set_mode, set_dpi, get_canvas_info,
)
from cli_anything.gimp.core.session import Session


# ── Project Tests ────────────────────────────────────────────────

class TestProject:
    def test_create_default(self):
        proj = create_project()
        assert proj["canvas"]["width"] == 1920
        assert proj["canvas"]["height"] == 1080
        assert proj["canvas"]["color_mode"] == "RGB"
        assert proj["version"] == "1.0"

    def test_create_with_dimensions(self):
        proj = create_project(width=800, height=600, dpi=150)
        assert proj["canvas"]["width"] == 800
        assert proj["canvas"]["height"] == 600
        assert proj["canvas"]["dpi"] == 150

    def test_create_with_profile(self):
        proj = create_project(profile="hd720p")
        assert proj["canvas"]["width"] == 1280
        assert proj["canvas"]["height"] == 720

    def test_create_invalid_mode(self):
        with pytest.raises(ValueError, match="Invalid color mode"):
            create_project(color_mode="XYZ")

    def test_create_invalid_dimensions(self):
        with pytest.raises(ValueError, match="must be positive"):
            create_project(width=0, height=100)

    def test_save_and_open(self):
        proj = create_project(name="test_project")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            save_project(proj, path)
            loaded = open_project(path)
            assert loaded["name"] == "test_project"
            assert loaded["canvas"]["width"] == 1920
        finally:
            os.unlink(path)

    def test_open_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            open_project("/nonexistent/path.json")

    def test_get_info(self):
        proj = create_project(name="info_test")
        info = get_project_info(proj)
        assert info["name"] == "info_test"
        assert info["layer_count"] == 0
        assert "canvas" in info

    def test_list_profiles(self):
        profiles = list_profiles()
        assert len(profiles) > 0
        names = [p["name"] for p in profiles]
        assert "hd1080p" in names
        assert "4k" in names


# ── Layer Tests ──────────────────────────────────────────────────

class TestLayers:
    def _make_project(self):
        return create_project()

    def test_add_layer(self):
        proj = self._make_project()
        layer = add_layer(proj, name="Test", layer_type="image")
        assert layer["name"] == "Test"
        assert layer["type"] == "image"
        assert len(proj["layers"]) == 1

    def test_add_multiple_layers(self):
        proj = self._make_project()
        add_layer(proj, name="Bottom")
        add_layer(proj, name="Top")
        assert len(proj["layers"]) == 2
        assert proj["layers"][0]["name"] == "Top"  # Top of stack

    def test_add_layer_with_position(self):
        proj = self._make_project()
        add_layer(proj, name="First")
        add_layer(proj, name="Second", position=1)
        assert proj["layers"][1]["name"] == "Second"

    def test_add_layer_invalid_mode(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Invalid blend mode"):
            add_layer(proj, blend_mode="invalid")

    def test_add_layer_invalid_opacity(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Opacity"):
            add_layer(proj, opacity=1.5)

    def test_remove_layer(self):
        proj = self._make_project()
        add_layer(proj, name="A")
        add_layer(proj, name="B")
        removed = remove_layer(proj, 0)
        assert removed["name"] == "B"
        assert len(proj["layers"]) == 1

    def test_remove_layer_invalid_index(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="No layers"):
            remove_layer(proj, 0)

    def test_duplicate_layer(self):
        proj = self._make_project()
        add_layer(proj, name="Original")
        dup = duplicate_layer(proj, 0)
        assert dup["name"] == "Original copy"
        assert len(proj["layers"]) == 2

    def test_move_layer(self):
        proj = self._make_project()
        add_layer(proj, name="A")
        add_layer(proj, name="B")
        add_layer(proj, name="C")
        move_layer(proj, 0, 2)
        assert proj["layers"][2]["name"] == "C"

    def test_set_property_opacity(self):
        proj = self._make_project()
        add_layer(proj, name="Test")
        set_layer_property(proj, 0, "opacity", 0.5)
        assert proj["layers"][0]["opacity"] == 0.5

    def test_set_property_visible(self):
        proj = self._make_project()
        add_layer(proj, name="Test")
        set_layer_property(proj, 0, "visible", "false")
        assert proj["layers"][0]["visible"] is False

    def test_set_property_name(self):
        proj = self._make_project()
        add_layer(proj, name="Old")
        set_layer_property(proj, 0, "name", "New")
        assert proj["layers"][0]["name"] == "New"

    def test_set_property_invalid(self):
        proj = self._make_project()
        add_layer(proj, name="Test")
        with pytest.raises(ValueError, match="Unknown property"):
            set_layer_property(proj, 0, "bogus", "value")

    def test_get_layer(self):
        proj = self._make_project()
        add_layer(proj, name="Test")
        layer = get_layer(proj, 0)
        assert layer["name"] == "Test"

    def test_list_layers(self):
        proj = self._make_project()
        add_layer(proj, name="A")
        add_layer(proj, name="B")
        result = list_layers(proj)
        assert len(result) == 2
        assert result[0]["name"] == "B"

    def test_layer_ids_unique(self):
        proj = self._make_project()
        l1 = add_layer(proj, name="A")
        l2 = add_layer(proj, name="B")
        assert l1["id"] != l2["id"]

    def test_solid_layer(self):
        proj = self._make_project()
        layer = add_layer(proj, name="Red", layer_type="solid", fill="#ff0000")
        assert layer["type"] == "solid"
        assert layer["fill"] == "#ff0000"

    def test_text_layer(self):
        proj = self._make_project()
        layer = add_layer(proj, name="Title", layer_type="text")
        assert layer["type"] == "text"
        assert "text" in layer
        assert "font_size" in layer


# ── Filter Tests ─────────────────────────────────────────────────

class TestFilters:
    def _make_project_with_layer(self):
        proj = create_project()
        add_layer(proj, name="Test")
        return proj

    def test_list_available(self):
        filters = list_available()
        assert len(filters) > 10
        names = [f["name"] for f in filters]
        assert "brightness" in names
        assert "gaussian_blur" in names

    def test_list_by_category(self):
        blurs = list_available(category="blur")
        assert all(f["category"] == "blur" for f in blurs)
        assert len(blurs) >= 3

    def test_get_filter_info(self):
        info = get_filter_info("brightness")
        assert info["name"] == "brightness"
        assert "factor" in info["params"]

    def test_get_filter_info_unknown(self):
        with pytest.raises(ValueError, match="Unknown filter"):
            get_filter_info("nonexistent")

    def test_validate_params(self):
        params = validate_params("brightness", {"factor": 1.5})
        assert params["factor"] == 1.5

    def test_validate_params_defaults(self):
        params = validate_params("brightness", {})
        assert params["factor"] == 1.0

    def test_validate_params_out_of_range(self):
        with pytest.raises(ValueError, match="maximum"):
            validate_params("brightness", {"factor": 100.0})

    def test_validate_params_unknown(self):
        with pytest.raises(ValueError, match="Unknown parameters"):
            validate_params("brightness", {"bogus": 1.0})

    def test_add_filter(self):
        proj = self._make_project_with_layer()
        result = add_filter(proj, "brightness", 0, {"factor": 1.2})
        assert result["name"] == "brightness"
        assert proj["layers"][0]["filters"][0]["name"] == "brightness"

    def test_add_filter_invalid_layer(self):
        proj = self._make_project_with_layer()
        with pytest.raises(IndexError):
            add_filter(proj, "brightness", 5, {})

    def test_add_filter_unknown(self):
        proj = self._make_project_with_layer()
        with pytest.raises(ValueError, match="Unknown filter"):
            add_filter(proj, "nonexistent", 0, {})

    def test_remove_filter(self):
        proj = self._make_project_with_layer()
        add_filter(proj, "brightness", 0, {"factor": 1.2})
        removed = remove_filter(proj, 0, 0)
        assert removed["name"] == "brightness"
        assert len(proj["layers"][0]["filters"]) == 0

    def test_set_filter_param(self):
        proj = self._make_project_with_layer()
        add_filter(proj, "brightness", 0, {"factor": 1.0})
        set_filter_param(proj, 0, "factor", 1.5, 0)
        assert proj["layers"][0]["filters"][0]["params"]["factor"] == 1.5

    def test_list_filters(self):
        proj = self._make_project_with_layer()
        add_filter(proj, "brightness", 0, {"factor": 1.2})
        add_filter(proj, "contrast", 0, {"factor": 1.1})
        result = list_filters(proj, 0)
        assert len(result) == 2
        assert result[0]["name"] == "brightness"
        assert result[1]["name"] == "contrast"

    def test_all_filters_have_valid_engine(self):
        valid_engines = {"pillow_enhance", "pillow_ops", "pillow_filter",
                         "pillow_transform", "custom"}
        for name, spec in FILTER_REGISTRY.items():
            assert spec["engine"] in valid_engines, f"Filter '{name}' has invalid engine"


# ── Canvas Tests ─────────────────────────────────────────────────

class TestCanvas:
    def _make_project(self):
        return create_project(width=800, height=600)

    def test_resize_canvas(self):
        proj = self._make_project()
        result = resize_canvas(proj, 1000, 800)
        assert proj["canvas"]["width"] == 1000
        assert proj["canvas"]["height"] == 800
        assert "old_size" in result

    def test_resize_canvas_with_anchor(self):
        proj = self._make_project()
        add_layer(proj, name="Test")
        resize_canvas(proj, 1000, 800, anchor="top-left")
        assert proj["layers"][0]["offset_x"] == 0
        assert proj["layers"][0]["offset_y"] == 0

    def test_resize_canvas_invalid_size(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="must be positive"):
            resize_canvas(proj, 0, 100)

    def test_scale_canvas(self):
        proj = self._make_project()
        add_layer(proj, name="Test", width=800, height=600)
        result = scale_canvas(proj, 400, 300)
        assert proj["canvas"]["width"] == 400
        assert proj["canvas"]["height"] == 300
        assert proj["layers"][0]["width"] == 400
        assert proj["layers"][0]["height"] == 300

    def test_crop_canvas(self):
        proj = self._make_project()
        result = crop_canvas(proj, 100, 100, 500, 400)
        assert proj["canvas"]["width"] == 400
        assert proj["canvas"]["height"] == 300

    def test_crop_canvas_out_of_bounds(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="exceeds canvas"):
            crop_canvas(proj, 0, 0, 1000, 1000)

    def test_crop_canvas_invalid_region(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Invalid crop"):
            crop_canvas(proj, 500, 500, 100, 100)

    def test_set_mode(self):
        proj = self._make_project()
        result = set_mode(proj, "RGBA")
        assert proj["canvas"]["color_mode"] == "RGBA"
        assert result["old_mode"] == "RGB"

    def test_set_mode_invalid(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Invalid color mode"):
            set_mode(proj, "XYZ")

    def test_set_dpi(self):
        proj = self._make_project()
        result = set_dpi(proj, 300)
        assert proj["canvas"]["dpi"] == 300

    def test_get_canvas_info(self):
        proj = self._make_project()
        info = get_canvas_info(proj)
        assert info["width"] == 800
        assert info["height"] == 600
        assert "megapixels" in info


# ── Session Tests ────────────────────────────────────────────────

class TestSession:
    def test_create_session(self):
        sess = Session()
        assert not sess.has_project()

    def test_set_project(self):
        sess = Session()
        proj = create_project()
        sess.set_project(proj)
        assert sess.has_project()

    def test_get_project_no_project(self):
        sess = Session()
        with pytest.raises(RuntimeError, match="No project loaded"):
            sess.get_project()

    def test_undo_redo(self):
        sess = Session()
        proj = create_project(name="original")
        sess.set_project(proj)

        sess.snapshot("change name")
        proj["name"] = "modified"

        assert proj["name"] == "modified"
        sess.undo()
        assert sess.get_project()["name"] == "original"
        sess.redo()
        assert sess.get_project()["name"] == "modified"

    def test_undo_empty(self):
        sess = Session()
        sess.set_project(create_project())
        with pytest.raises(RuntimeError, match="Nothing to undo"):
            sess.undo()

    def test_redo_empty(self):
        sess = Session()
        sess.set_project(create_project())
        with pytest.raises(RuntimeError, match="Nothing to redo"):
            sess.redo()

    def test_snapshot_clears_redo(self):
        sess = Session()
        proj = create_project(name="v1")
        sess.set_project(proj)

        sess.snapshot("v2")
        proj["name"] = "v2"

        sess.undo()
        assert sess.get_project()["name"] == "v1"

        # New snapshot should clear redo stack
        sess.snapshot("v3")
        sess.get_project()["name"] = "v3"

        with pytest.raises(RuntimeError, match="Nothing to redo"):
            sess.redo()

    def test_status(self):
        sess = Session()
        proj = create_project(name="test")
        sess.set_project(proj, "/tmp/test.json")
        status = sess.status()
        assert status["has_project"] is True
        assert status["project_path"] == "/tmp/test.json"
        assert status["undo_count"] == 0

    def test_save_session(self):
        sess = Session()
        proj = create_project(name="save_test")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            sess.set_project(proj, path)
            saved = sess.save_session()
            assert os.path.exists(saved)
            with open(saved) as f:
                loaded = json.load(f)
            assert loaded["name"] == "save_test"
        finally:
            os.unlink(path)

    def test_list_history(self):
        sess = Session()
        proj = create_project()
        sess.set_project(proj)
        sess.snapshot("action 1")
        sess.snapshot("action 2")
        history = sess.list_history()
        assert len(history) == 2
        assert history[0]["description"] == "action 2"

    def test_max_undo(self):
        sess = Session()
        sess.MAX_UNDO = 5
        proj = create_project()
        sess.set_project(proj)
        for i in range(10):
            sess.snapshot(f"action {i}")
        assert len(sess._undo_stack) == 5


# ── Concurrent Save Tests ───────────────────────────────────────

class TestLockedSaveJson:
    """Tests for _locked_save_json atomic file writes."""

    def test_basic_save(self, tmp_path):
        from cli_anything.gimp.core.session import _locked_save_json
        path = str(tmp_path / "test.json")
        _locked_save_json(path, {"key": "value"}, indent=2)
        with open(path) as f:
            data = json.load(f)
        assert data == {"key": "value"}

    def test_overwrite_existing(self, tmp_path):
        from cli_anything.gimp.core.session import _locked_save_json
        path = str(tmp_path / "test.json")
        _locked_save_json(path, {"version": 1}, indent=2)
        _locked_save_json(path, {"version": 2}, indent=2)
        with open(path) as f:
            data = json.load(f)
        assert data == {"version": 2}

    def test_overwrite_shorter_data(self, tmp_path):
        """Ensure truncation works — shorter data doesn't leave old bytes."""
        from cli_anything.gimp.core.session import _locked_save_json
        path = str(tmp_path / "test.json")
        _locked_save_json(path, {"key": "a" * 1000}, indent=2)
        _locked_save_json(path, {"k": 1}, indent=2)
        with open(path) as f:
            data = json.load(f)
        assert data == {"k": 1}

    def test_creates_parent_dirs(self, tmp_path):
        from cli_anything.gimp.core.session import _locked_save_json
        path = str(tmp_path / "nested" / "dir" / "test.json")
        _locked_save_json(path, {"nested": True})
        with open(path) as f:
            data = json.load(f)
        assert data == {"nested": True}

    def test_concurrent_writes_produce_valid_json(self, tmp_path):
        """Multiple threads writing to the same file should not corrupt it."""
        from cli_anything.gimp.core.session import _locked_save_json
        import threading

        path = str(tmp_path / "concurrent.json")
        errors = []

        def writer(thread_id):
            try:
                for i in range(50):
                    _locked_save_json(
                        path,
                        {"thread": thread_id, "iteration": i},
                        indent=2, sort_keys=True,
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors during concurrent writes: {errors}"
        # Final file must be valid JSON
        with open(path) as f:
            data = json.load(f)
        assert "thread" in data
        assert "iteration" in data
