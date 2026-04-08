"""Unit tests for Openscreen CLI — no ffmpeg backend required.

Tests the core data model: session, project, timeline regions, crop.
All operations are in-memory JSON manipulation.
"""

import json
import os
import tempfile

import pytest

from cli_anything.openscreen.core.session import Session
from cli_anything.openscreen.core import project as proj_mod
from cli_anything.openscreen.core import timeline as tl_mod
from cli_anything.openscreen.core import export as export_mod


# ── Session Tests ─────────────────────────────────────────────────────────

class TestSession:
    def test_new_session(self):
        s = Session()
        assert s.session_id.startswith("session_")
        assert not s.is_open
        assert not s.is_modified

    def test_new_session_with_id(self):
        s = Session("my_session")
        assert s.session_id == "my_session"

    def test_new_project(self):
        s = Session()
        s.new_project()
        assert s.is_open
        assert not s.is_modified
        assert s.editor["aspectRatio"] == "16:9"
        assert s.editor["padding"] == 50

    def test_new_project_with_video(self):
        s = Session()
        s.new_project("/tmp/test.mp4")
        assert s.is_open
        assert s.data["media"]["screenVideoPath"] == "/tmp/test.mp4"

    def test_undo_redo(self):
        s = Session()
        s.new_project()
        # No undo available on fresh project
        assert not s.undo()

        # Make a change
        s.checkpoint()
        s.editor["padding"] = 30

        # Undo should restore
        assert s.undo()
        assert s.editor["padding"] == 50

        # Redo should reapply
        assert s.redo()
        assert s.editor["padding"] == 30

    def test_undo_clears_redo(self):
        s = Session()
        s.new_project()

        s.checkpoint()
        s.editor["padding"] = 30

        s.checkpoint()
        s.editor["padding"] = 20

        assert s.undo()
        assert s.editor["padding"] == 30

        # New change should clear redo stack
        s.checkpoint()
        s.editor["padding"] = 40
        assert not s.redo()

    def test_save_load_project(self):
        s = Session()
        s.new_project()
        s.checkpoint()
        s.editor["padding"] = 42

        with tempfile.NamedTemporaryFile(suffix=".openscreen", delete=False) as f:
            path = f.name

        try:
            s.save_project(path)
            assert not s.is_modified

            s2 = Session()
            s2.open_project(path)
            assert s2.is_open
            assert s2.editor["padding"] == 42
        finally:
            os.unlink(path)

    def test_open_nonexistent(self):
        s = Session()
        with pytest.raises(FileNotFoundError):
            s.open_project("/nonexistent/project.openscreen")

    def test_save_without_path(self):
        s = Session()
        s.new_project()
        with pytest.raises(RuntimeError, match="No save path"):
            s.save_project()

    def test_status(self):
        s = Session()
        status = s.status()
        assert status["project_open"] is False

        s.new_project()
        status = s.status()
        assert status["project_open"] is True
        assert status["zoom_region_count"] == 0

    # ── Extra tests from auto version ──────────────────────────────────

    def test_editor_raises_when_not_open(self):
        s = Session()
        with pytest.raises(RuntimeError):
            _ = s.editor

    def test_checkpoint_adds_to_undo(self):
        s = Session()
        s.new_project()
        before = len(s._undo_stack)
        s.checkpoint()
        assert len(s._undo_stack) == before + 1

    def test_undo_stack_limit_50(self):
        s = Session()
        s.new_project()
        for i in range(60):
            s.checkpoint()
        assert len(s._undo_stack) <= 50

    def test_is_modified_after_checkpoint(self):
        s = Session()
        s.new_project()
        assert not s.is_modified
        s.checkpoint()
        assert s.is_modified

    def test_open_invalid_json_raises(self, tmp_path):
        path = tmp_path / "bad.openscreen"
        path.write_text("not json at all")
        s = Session()
        with pytest.raises((RuntimeError, ValueError, Exception)):
            s.open_project(str(path))


# ── Project Tests ─────────────────────────────────────────────────────────

class TestProject:
    def test_new_project(self):
        s = Session()
        result = proj_mod.new_project(s)
        assert result["status"] == "created"
        assert s.is_open

    def test_info(self):
        s = Session()
        s.new_project()
        result = proj_mod.info(s)
        assert result["version"] == 2
        assert result["aspect_ratio"] == "16:9"
        assert result["zoom_regions"] == 0

    def test_info_without_project(self):
        s = Session()
        with pytest.raises(RuntimeError, match="No project"):
            proj_mod.info(s)

    def test_set_setting(self):
        s = Session()
        s.new_project()
        result = proj_mod.set_setting(s, "padding", 30)
        assert result["value"] == 30
        assert s.editor["padding"] == 30

    def test_set_invalid_setting(self):
        s = Session()
        s.new_project()
        with pytest.raises(ValueError, match="Unknown setting"):
            proj_mod.set_setting(s, "nonexistent_key", 42)

    # ── Extra tests from auto version ──────────────────────────────────

    def test_set_setting_aspectRatio(self):
        s = Session()
        s.new_project()
        proj_mod.set_setting(s, "aspectRatio", "9:16")
        assert s.editor["aspectRatio"] == "9:16"

    def test_set_setting_invalid_aspectRatio(self):
        s = Session()
        s.new_project()
        with pytest.raises(ValueError):
            proj_mod.set_setting(s, "aspectRatio", "invalid")

    def test_set_setting_exportQuality(self):
        s = Session()
        s.new_project()
        proj_mod.set_setting(s, "exportQuality", "source")
        assert s.editor["exportQuality"] == "source"

    def test_set_setting_exportFormat(self):
        s = Session()
        s.new_project()
        proj_mod.set_setting(s, "exportFormat", "gif")
        assert s.editor["exportFormat"] == "gif"

    def test_set_setting_invalid_exportFormat(self):
        s = Session()
        s.new_project()
        with pytest.raises(ValueError):
            proj_mod.set_setting(s, "exportFormat", "avi")

    def test_set_setting_padding_valid(self):
        s = Session()
        s.new_project()
        proj_mod.set_setting(s, "padding", 30)
        assert s.editor["padding"] == 30

    def test_set_setting_padding_too_large(self):
        s = Session()
        s.new_project()
        with pytest.raises(ValueError):
            proj_mod.set_setting(s, "padding", 101)

    def test_set_setting_calls_checkpoint(self):
        s = Session()
        s.new_project()
        proj_mod.set_setting(s, "padding", 10)
        assert len(s._undo_stack) >= 1

    def test_crop_region_validation_in_settings(self):
        s = Session()
        s.new_project()
        valid_crop = {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8}
        proj_mod.set_setting(s, "cropRegion", valid_crop)
        assert s.editor["cropRegion"] == valid_crop

    def test_crop_region_overflow_raises(self):
        s = Session()
        s.new_project()
        with pytest.raises(ValueError):
            proj_mod.set_setting(s, "cropRegion", {"x": 0.5, "y": 0.0, "width": 0.8, "height": 1.0})


# ── Zoom Tests ────────────────────────────────────────────────────────────

class TestZoom:
    def test_add_zoom(self):
        s = Session()
        s.new_project()
        result = tl_mod.add_zoom_region(s, 1000, 5000, depth=3, focus_x=0.5, focus_y=0.5)
        assert result["startMs"] == 1000
        assert result["endMs"] == 5000
        assert result["depth"] == 3
        assert "id" in result

    def test_list_zoom(self):
        s = Session()
        s.new_project()
        assert len(tl_mod.list_zoom_regions(s)) == 0
        tl_mod.add_zoom_region(s, 1000, 2000)
        assert len(tl_mod.list_zoom_regions(s)) == 1

    def test_remove_zoom(self):
        s = Session()
        s.new_project()
        z = tl_mod.add_zoom_region(s, 1000, 2000)
        tl_mod.remove_zoom_region(s, z["id"])
        assert len(tl_mod.list_zoom_regions(s)) == 0

    def test_remove_nonexistent_zoom(self):
        s = Session()
        s.new_project()
        with pytest.raises(ValueError, match="not found"):
            tl_mod.remove_zoom_region(s, "nonexistent_id")

    def test_invalid_depth(self):
        s = Session()
        s.new_project()
        with pytest.raises(ValueError, match="Invalid depth"):
            tl_mod.add_zoom_region(s, 1000, 2000, depth=7)

    def test_invalid_focus(self):
        s = Session()
        s.new_project()
        with pytest.raises(ValueError, match="Focus coordinates"):
            tl_mod.add_zoom_region(s, 1000, 2000, focus_x=1.5)

    def test_invalid_time_range(self):
        s = Session()
        s.new_project()
        with pytest.raises(ValueError, match="end_ms.*must be"):
            tl_mod.add_zoom_region(s, 5000, 1000)

    def test_zoom_undo(self):
        s = Session()
        s.new_project()
        tl_mod.add_zoom_region(s, 1000, 2000)
        assert len(tl_mod.list_zoom_regions(s)) == 1
        s.undo()
        assert len(tl_mod.list_zoom_regions(s)) == 0

    # ── Extra tests from auto version ──────────────────────────────────

    def test_add_zoom_focus(self):
        s = Session()
        s.new_project()
        region = tl_mod.add_zoom_region(s, 0, 2000, depth=3, focus_x=0.3, focus_y=0.7)
        assert region["focus"]["cx"] == 0.3
        assert region["focus"]["cy"] == 0.7

    def test_list_zoom_sorted(self):
        s = Session()
        s.new_project()
        tl_mod.add_zoom_region(s, 5000, 8000, depth=1)
        tl_mod.add_zoom_region(s, 1000, 3000, depth=2)
        regions = tl_mod.list_zoom_regions(s)
        starts = [r["startMs"] for r in regions]
        assert starts == sorted(starts)

    def test_update_zoom_region(self):
        s = Session()
        s.new_project()
        region = tl_mod.add_zoom_region(s, 1000, 3000, depth=1)
        updated = tl_mod.update_zoom_region(s, region["id"], depth=4, focus_x=0.8)
        assert updated["depth"] == 4
        assert updated["focus"]["cx"] == 0.8

    def test_update_zoom_nonexistent(self):
        s = Session()
        s.new_project()
        with pytest.raises((ValueError, KeyError)):
            tl_mod.update_zoom_region(s, "fake-id")

    def test_zoom_depth_map_values(self):
        # ZOOM_DEPTHS maps depth int -> scale factor
        from cli_anything.openscreen.core.timeline import ZOOM_DEPTHS
        assert ZOOM_DEPTHS[1] == 1.25
        assert ZOOM_DEPTHS[6] == 5.0

    def test_add_zoom_calls_checkpoint(self):
        s = Session()
        s.new_project()
        initial = len(s._undo_stack)
        tl_mod.add_zoom_region(s, 0, 1000, depth=2)
        assert len(s._undo_stack) > initial


# ── Speed Tests ───────────────────────────────────────────────────────────

class TestSpeed:
    def test_add_speed(self):
        s = Session()
        s.new_project()
        result = tl_mod.add_speed_region(s, 5000, 10000, speed=2.0)
        assert result["speed"] == 2.0

    def test_invalid_speed(self):
        s = Session()
        s.new_project()
        with pytest.raises(ValueError, match="Invalid speed"):
            tl_mod.add_speed_region(s, 1000, 2000, speed=3.0)

    def test_list_and_remove(self):
        s = Session()
        s.new_project()
        r = tl_mod.add_speed_region(s, 1000, 2000, speed=1.5)
        assert len(tl_mod.list_speed_regions(s)) == 1
        tl_mod.remove_speed_region(s, r["id"])
        assert len(tl_mod.list_speed_regions(s)) == 0

    # ── Extra tests from auto version ──────────────────────────────────

    def test_add_speed_all_valid_values(self):
        from cli_anything.openscreen.core.timeline import VALID_SPEEDS
        s = Session()
        s.new_project()
        for speed in VALID_SPEEDS:
            region = tl_mod.add_speed_region(s, 0, 1000, speed=speed)
            assert region["speed"] == speed

    def test_list_speed_sorted(self):
        s = Session()
        s.new_project()
        tl_mod.add_speed_region(s, 5000, 8000, speed=1.5)
        tl_mod.add_speed_region(s, 1000, 3000, speed=2.0)
        regions = tl_mod.list_speed_regions(s)
        starts = [r["startMs"] for r in regions]
        assert starts == sorted(starts)

    def test_remove_speed_nonexistent(self):
        s = Session()
        s.new_project()
        with pytest.raises((ValueError, KeyError)):
            tl_mod.remove_speed_region(s, "nonexistent")


# ── Trim Tests ────────────────────────────────────────────────────────────

class TestTrim:
    def test_add_trim(self):
        s = Session()
        s.new_project()
        result = tl_mod.add_trim_region(s, 0, 1000)
        assert result["startMs"] == 0
        assert result["endMs"] == 1000

    def test_list_and_remove(self):
        s = Session()
        s.new_project()
        r = tl_mod.add_trim_region(s, 0, 1000)
        assert len(tl_mod.list_trim_regions(s)) == 1
        tl_mod.remove_trim_region(s, r["id"])
        assert len(tl_mod.list_trim_regions(s)) == 0

    # ── Extra tests from auto version ──────────────────────────────────

    def test_add_trim_zero_start(self):
        s = Session()
        s.new_project()
        region = tl_mod.add_trim_region(s, 0, 1000)
        assert region["startMs"] == 0

    def test_list_trim_sorted(self):
        s = Session()
        s.new_project()
        tl_mod.add_trim_region(s, 8000, 10000)
        tl_mod.add_trim_region(s, 1000, 3000)
        regions = tl_mod.list_trim_regions(s)
        starts = [r["startMs"] for r in regions]
        assert starts == sorted(starts)

    def test_remove_trim_nonexistent(self):
        s = Session()
        s.new_project()
        with pytest.raises((ValueError, KeyError)):
            tl_mod.remove_trim_region(s, "fake")


# ── Crop Tests ────────────────────────────────────────────────────────────

class TestCrop:
    def test_default_crop(self):
        s = Session()
        s.new_project()
        crop = tl_mod.get_crop(s)
        assert crop == {"x": 0, "y": 0, "width": 1, "height": 1}

    def test_set_crop(self):
        s = Session()
        s.new_project()
        result = tl_mod.set_crop(s, 0.1, 0.1, 0.8, 0.8)
        assert result["x"] == 0.1
        assert result["width"] == 0.8

    def test_invalid_crop(self):
        s = Session()
        s.new_project()
        with pytest.raises(ValueError):
            tl_mod.set_crop(s, 0, 0, 1.5, 1)

    def test_crop_out_of_bounds(self):
        s = Session()
        s.new_project()
        with pytest.raises(ValueError, match="beyond frame"):
            tl_mod.set_crop(s, 0.5, 0.5, 0.6, 0.6)

    # ── Extra tests from auto version ──────────────────────────────────

    def test_set_crop_overflow_x(self):
        s = Session()
        s.new_project()
        with pytest.raises(ValueError):
            tl_mod.set_crop(s, 0.5, 0.0, 0.6, 1.0)

    def test_set_crop_overflow_y(self):
        s = Session()
        s.new_project()
        with pytest.raises(ValueError):
            tl_mod.set_crop(s, 0.0, 0.5, 1.0, 0.6)

    def test_set_crop_negative_raises(self):
        s = Session()
        s.new_project()
        with pytest.raises(ValueError):
            tl_mod.set_crop(s, -0.1, 0.0, 1.0, 1.0)

    def test_set_crop_calls_checkpoint(self):
        s = Session()
        s.new_project()
        initial = len(s._undo_stack)
        tl_mod.set_crop(s, 0.0, 0.0, 0.5, 0.5)
        assert len(s._undo_stack) > initial

    def test_crop_full_frame_valid(self):
        s = Session()
        s.new_project()
        crop = tl_mod.set_crop(s, 0.0, 0.0, 1.0, 1.0)
        assert crop["x"] == 0.0


# ── Annotation Tests ──────────────────────────────────────────────────────

class TestAnnotation:
    def test_add_text_annotation(self):
        s = Session()
        s.new_project()
        result = tl_mod.add_text_annotation(s, 1000, 3000, "Hello World")
        assert result["type"] == "text"
        assert result["textContent"] == "Hello World"

    def test_list_and_remove(self):
        s = Session()
        s.new_project()
        a = tl_mod.add_text_annotation(s, 1000, 3000, "Test")
        assert len(tl_mod.list_annotations(s)) == 1
        tl_mod.remove_annotation(s, a["id"])
        assert len(tl_mod.list_annotations(s)) == 0

    # ── Extra tests from auto version ──────────────────────────────────

    def test_add_annotation_position(self):
        s = Session()
        s.new_project()
        region = tl_mod.add_text_annotation(s, 0, 2000, "Positioned", x=0.25, y=0.75)
        assert region["position"]["x"] == 0.25
        assert region["position"]["y"] == 0.75

    def test_list_annotations_sorted(self):
        s = Session()
        s.new_project()
        tl_mod.add_text_annotation(s, 5000, 8000, "Later")
        tl_mod.add_text_annotation(s, 1000, 3000, "Earlier")
        regions = tl_mod.list_annotations(s)
        starts = [r["startMs"] for r in regions]
        assert starts == sorted(starts)

    def test_update_annotation_text(self):
        s = Session()
        s.new_project()
        region = tl_mod.add_text_annotation(s, 0, 2000, "original")
        tl_mod.update_annotation(s, region["id"], text_content="updated")
        regions = tl_mod.list_annotations(s)
        assert regions[0]["textContent"] == "updated"

    def test_update_annotation_nonexistent(self):
        s = Session()
        s.new_project()
        with pytest.raises((ValueError, KeyError)):
            tl_mod.update_annotation(s, "fake-id", text_content="x")

    def test_annotation_style_fields(self):
        s = Session()
        s.new_project()
        region = tl_mod.add_text_annotation(s, 0, 1000, "Styled", color="#ff0000", font_size=32)
        assert region["style"]["color"] == "#ff0000"
        assert region["style"]["fontSize"] == 32


# ── Integration Tests ─────────────────────────────────────────────────────

class TestIntegration:
    def test_full_workflow(self):
        """Test a complete project workflow: create, edit, save, reopen."""
        s = Session()
        s.new_project()

        # Set settings
        proj_mod.set_setting(s, "aspectRatio", "16:9")
        proj_mod.set_setting(s, "wallpaper", "gradient_dark")
        proj_mod.set_setting(s, "padding", 40)

        # Add regions
        z1 = tl_mod.add_zoom_region(s, 2000, 5000, depth=3, focus_x=0.7, focus_y=0.3)
        z2 = tl_mod.add_zoom_region(s, 8000, 12000, depth=4, focus_x=0.5, focus_y=0.5)
        sp = tl_mod.add_speed_region(s, 15000, 20000, speed=2.0)
        tr = tl_mod.add_trim_region(s, 0, 500)
        ann = tl_mod.add_text_annotation(s, 5000, 7000, "Click here!")
        tl_mod.set_crop(s, 0, 0, 1, 1)

        # Verify counts
        info = proj_mod.info(s)
        assert info["zoom_regions"] == 2
        assert info["speed_regions"] == 1
        assert info["trim_regions"] == 1
        assert info["annotations"] == 1

        # Save and reopen
        with tempfile.NamedTemporaryFile(suffix=".openscreen", delete=False) as f:
            path = f.name
        try:
            s.save_project(path)

            s2 = Session()
            s2.open_project(path)
            info2 = proj_mod.info(s2)
            assert info2["zoom_regions"] == 2
            assert info2["speed_regions"] == 1
            assert info2["annotations"] == 1
        finally:
            os.unlink(path)

    def test_export_presets(self):
        """Test that export presets are available."""
        presets = export_mod.list_presets()
        assert len(presets) > 0
        assert any(p["name"] == "mp4_good" for p in presets)

    # ── Extra tests from auto version ──────────────────────────────────

    def test_undo_redo_zoom_workflow(self):
        s = Session()
        s.new_project()
        tl_mod.add_zoom_region(s, 1000, 3000, depth=2)
        assert len(tl_mod.list_zoom_regions(s)) == 1

        s.undo()
        assert len(tl_mod.list_zoom_regions(s)) == 0

        s.redo()
        assert len(tl_mod.list_zoom_regions(s)) == 1

    def test_multiple_undo_levels(self):
        s = Session()
        s.new_project()
        for i in range(5):
            tl_mod.add_zoom_region(s, i * 1000, (i + 1) * 1000, depth=1)

        assert len(tl_mod.list_zoom_regions(s)) == 5
        for _ in range(5):
            s.undo()
        assert len(tl_mod.list_zoom_regions(s)) == 0

    def test_timeline_boundaries(self):
        s = Session()
        s.new_project()
        tl_mod.add_zoom_region(s, 1000, 3000, depth=1)
        tl_mod.add_speed_region(s, 2000, 5000, speed=1.5)
        tl_mod.add_trim_region(s, 4000, 6000)

        boundaries = tl_mod.get_timeline_boundaries(s)
        assert 0 in boundaries
        assert 1000 in boundaries
        assert 2000 in boundaries
        assert 3000 in boundaries
        assert 4000 in boundaries
        assert 5000 in boundaries
        assert 6000 in boundaries

    def test_active_regions_at(self):
        s = Session()
        s.new_project()
        tl_mod.add_zoom_region(s, 1000, 5000, depth=2)
        tl_mod.add_speed_region(s, 2000, 4000, speed=1.5)
        tl_mod.add_trim_region(s, 6000, 8000)

        active = tl_mod.get_active_regions_at(s, 3000)
        assert len(active["zoom"]) == 1
        assert len(active["speed"]) == 1
        assert len(active["trim"]) == 0

        active2 = tl_mod.get_active_regions_at(s, 7000)
        assert len(active2["trim"]) == 1
        assert len(active2["zoom"]) == 0

    def test_project_set_triggers_undo(self):
        s = Session()
        s.new_project()
        proj_mod.set_setting(s, "padding", 10)
        proj_mod.set_setting(s, "padding", 30)
        assert s.editor["padding"] == 30
        s.undo()
        assert s.editor["padding"] == 10
