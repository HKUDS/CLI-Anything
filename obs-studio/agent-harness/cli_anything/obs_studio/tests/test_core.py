"""Unit tests for OBS Studio CLI core modules.

Tests use synthetic data only -- no OBS Studio installation required.
"""

import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.obs_studio.core.project import create_project, open_project, save_project, get_project_info
from cli_anything.obs_studio.core.scenes import add_scene, remove_scene, duplicate_scene, set_active_scene, list_scenes
from cli_anything.obs_studio.core.sources import (
    add_source, remove_source, duplicate_source, set_source_property,
    transform_source, list_sources, get_source, SOURCE_TYPES,
)
from cli_anything.obs_studio.core.filters import (
    add_filter, remove_filter, set_filter_param, list_filters,
    list_available_filters, FILTER_TYPES,
)
from cli_anything.obs_studio.core.audio import (
    add_audio_source, remove_audio_source, set_volume, mute, unmute,
    set_monitor, set_balance, set_sync_offset, list_audio, MONITOR_TYPES,
)
from cli_anything.obs_studio.core.transitions import (
    add_transition, remove_transition, set_duration, set_active_transition,
    list_transitions, TRANSITION_TYPES,
)
from cli_anything.obs_studio.core.output import (
    set_streaming, set_recording, set_output_settings, get_output_info,
    list_encoding_presets, ENCODING_PRESETS, VALID_SERVICES, VALID_RECORDING_FORMATS,
)
from cli_anything.obs_studio.core.session import Session


# -- Project Tests -----------------------------------------------------------

class TestProject:
    def test_create_default(self):
        proj = create_project()
        assert proj["settings"]["output_width"] == 1920
        assert proj["settings"]["output_height"] == 1080
        assert proj["settings"]["fps"] == 30
        assert proj["version"] == "1.0"
        assert len(proj["scenes"]) == 1

    def test_create_with_dimensions(self):
        proj = create_project(output_width=1280, output_height=720, fps=60)
        assert proj["settings"]["output_width"] == 1280
        assert proj["settings"]["output_height"] == 720
        assert proj["settings"]["fps"] == 60

    def test_create_with_encoder(self):
        proj = create_project(encoder="nvenc")
        assert proj["settings"]["encoder"] == "nvenc"

    def test_create_invalid_resolution(self):
        with pytest.raises(ValueError, match="must be positive"):
            create_project(output_width=0)

    def test_create_invalid_fps(self):
        with pytest.raises(ValueError, match="must be positive"):
            create_project(fps=0)

    def test_create_invalid_encoder(self):
        with pytest.raises(ValueError, match="Invalid encoder"):
            create_project(encoder="bogus")

    def test_create_invalid_video_bitrate(self):
        with pytest.raises(ValueError, match="at least 100"):
            create_project(video_bitrate=10)

    def test_create_invalid_audio_bitrate(self):
        with pytest.raises(ValueError, match="at least 32"):
            create_project(audio_bitrate=8)

    def test_save_and_open(self):
        proj = create_project(name="test_proj")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            save_project(proj, path)
            loaded = open_project(path)
            assert loaded["name"] == "test_proj"
            assert loaded["settings"]["output_width"] == 1920
        finally:
            os.unlink(path)

    def test_open_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            open_project("/nonexistent/path.json")

    def test_open_invalid(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump({"foo": "bar"}, f)
            path = f.name
        try:
            with pytest.raises(ValueError, match="Invalid"):
                open_project(path)
        finally:
            os.unlink(path)

    def test_get_info(self):
        proj = create_project(name="info_test")
        info = get_project_info(proj)
        assert info["name"] == "info_test"
        assert info["counts"]["scenes"] == 1
        assert "settings" in info

    def test_default_project_has_transitions(self):
        proj = create_project()
        assert len(proj["transitions"]) == 2

    def test_default_project_has_streaming(self):
        proj = create_project()
        assert proj["streaming"]["service"] == "twitch"

    def test_default_project_has_recording(self):
        proj = create_project()
        assert proj["recording"]["format"] == "mkv"

    def test_create_with_name(self):
        proj = create_project(name="my_stream")
        assert proj["name"] == "my_stream"


# -- Scene Tests -------------------------------------------------------------

class TestScenes:
    def _make_project(self):
        return create_project()

    def test_add_scene(self):
        proj = self._make_project()
        scene = add_scene(proj, name="BRB")
        assert scene["name"] == "BRB"
        assert len(proj["scenes"]) == 2

    def test_add_scene_unique_name(self):
        proj = self._make_project()
        s1 = add_scene(proj, name="Game")
        s2 = add_scene(proj, name="Game")
        assert s1["name"] != s2["name"]

    def test_add_scene_unique_ids(self):
        proj = self._make_project()
        s1 = add_scene(proj, name="A")
        s2 = add_scene(proj, name="B")
        assert s1["id"] != s2["id"]

    def test_remove_scene(self):
        proj = self._make_project()
        add_scene(proj, name="Extra")
        removed = remove_scene(proj, 1)
        assert removed["name"] == "Extra"
        assert len(proj["scenes"]) == 1

    def test_remove_last_scene_fails(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Cannot remove the last scene"):
            remove_scene(proj, 0)

    def test_remove_scene_invalid_index(self):
        proj = self._make_project()
        with pytest.raises(IndexError):
            remove_scene(proj, 99)

    def test_duplicate_scene(self):
        proj = self._make_project()
        dup = duplicate_scene(proj, 0)
        assert "Copy" in dup["name"]
        assert len(proj["scenes"]) == 2
        assert dup["id"] != proj["scenes"][0]["id"]

    def test_set_active_scene(self):
        proj = self._make_project()
        add_scene(proj, name="BRB")
        result = set_active_scene(proj, 1)
        assert result["index"] == 1
        assert proj["active_scene"] == 1

    def test_set_active_scene_invalid(self):
        proj = self._make_project()
        with pytest.raises(IndexError):
            set_active_scene(proj, 99)

    def test_list_scenes(self):
        proj = self._make_project()
        add_scene(proj, name="BRB")
        result = list_scenes(proj)
        assert len(result) == 2
        assert result[0]["active"] is True
        assert result[1]["active"] is False

    def test_remove_scene_fixes_active(self):
        proj = self._make_project()
        add_scene(proj, name="A")
        add_scene(proj, name="B")
        proj["active_scene"] = 2
        remove_scene(proj, 2)
        assert proj["active_scene"] <= len(proj["scenes"]) - 1


# -- Source Tests ------------------------------------------------------------

class TestSources:
    def _make_project(self):
        return create_project()

    def test_add_source_video_capture(self):
        proj = self._make_project()
        src = add_source(proj, "video_capture", name="Camera")
        assert src["name"] == "Camera"
        assert src["type"] == "video_capture"
        assert len(proj["scenes"][0]["sources"]) == 1

    def test_add_source_all_types(self):
        proj = self._make_project()
        for stype in SOURCE_TYPES:
            src = add_source(proj, stype)
            assert src["type"] == stype
        assert len(proj["scenes"][0]["sources"]) == len(SOURCE_TYPES)

    def test_add_source_invalid_type(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Unknown source type"):
            add_source(proj, "nonexistent")

    def test_add_source_with_position(self):
        proj = self._make_project()
        src = add_source(proj, "image", position={"x": 100, "y": 200})
        assert src["position"]["x"] == 100.0
        assert src["position"]["y"] == 200.0

    def test_add_source_with_size(self):
        proj = self._make_project()
        src = add_source(proj, "color", size={"width": 800, "height": 600})
        assert src["size"]["width"] == 800
        assert src["size"]["height"] == 600

    def test_add_source_invalid_size(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="must be positive"):
            add_source(proj, "color", size={"width": 0, "height": 600})

    def test_add_source_with_settings(self):
        proj = self._make_project()
        src = add_source(proj, "browser", settings={"url": "https://example.com"})
        assert src["settings"]["url"] == "https://example.com"

    def test_add_source_unique_names(self):
        proj = self._make_project()
        s1 = add_source(proj, "text", name="Label")
        s2 = add_source(proj, "text", name="Label")
        assert s1["name"] != s2["name"]

    def test_remove_source(self):
        proj = self._make_project()
        add_source(proj, "image", name="BG")
        removed = remove_source(proj, 0)
        assert removed["name"] == "BG"
        assert len(proj["scenes"][0]["sources"]) == 0

    def test_remove_source_invalid_index(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="No source"):
            remove_source(proj, 0)

    def test_duplicate_source(self):
        proj = self._make_project()
        add_source(proj, "text", name="Title")
        dup = duplicate_source(proj, 0)
        assert "Copy" in dup["name"]
        assert len(proj["scenes"][0]["sources"]) == 2

    def test_set_source_property_visible(self):
        proj = self._make_project()
        add_source(proj, "image")
        set_source_property(proj, 0, "visible", "false")
        assert proj["scenes"][0]["sources"][0]["visible"] is False

    def test_set_source_property_opacity(self):
        proj = self._make_project()
        add_source(proj, "image")
        set_source_property(proj, 0, "opacity", 0.5)
        assert proj["scenes"][0]["sources"][0]["opacity"] == 0.5

    def test_set_source_property_invalid(self):
        proj = self._make_project()
        add_source(proj, "image")
        with pytest.raises(ValueError, match="Unknown source property"):
            set_source_property(proj, 0, "bogus", "val")

    def test_set_source_property_opacity_range(self):
        proj = self._make_project()
        add_source(proj, "image")
        with pytest.raises(ValueError, match="must be between"):
            set_source_property(proj, 0, "opacity", 2.0)

    def test_transform_source_position(self):
        proj = self._make_project()
        add_source(proj, "image")
        src = transform_source(proj, 0, position={"x": 100, "y": 200})
        assert src["position"]["x"] == 100.0

    def test_transform_source_size(self):
        proj = self._make_project()
        add_source(proj, "image")
        src = transform_source(proj, 0, size={"width": 640, "height": 480})
        assert src["size"]["width"] == 640

    def test_transform_source_crop(self):
        proj = self._make_project()
        add_source(proj, "image")
        src = transform_source(proj, 0, crop={"top": 10, "bottom": 20, "left": 5, "right": 5})
        assert src["crop"]["top"] == 10

    def test_transform_source_rotation(self):
        proj = self._make_project()
        add_source(proj, "image")
        src = transform_source(proj, 0, rotation=45.0)
        assert src["rotation"] == 45.0

    def test_list_sources(self):
        proj = self._make_project()
        add_source(proj, "image", name="BG")
        add_source(proj, "text", name="Title")
        result = list_sources(proj)
        assert len(result) == 2

    def test_get_source(self):
        proj = self._make_project()
        add_source(proj, "image", name="Test")
        src = get_source(proj, 0)
        assert src["name"] == "Test"

    def test_source_default_properties(self):
        proj = self._make_project()
        src = add_source(proj, "color")
        assert src["visible"] is True
        assert src["locked"] is False
        assert src["opacity"] == 1.0
        assert src["rotation"] == 0


# -- Filter Tests ------------------------------------------------------------

class TestFilters:
    def _make_project_with_source(self):
        proj = create_project()
        add_source(proj, "video_capture", name="Camera")
        return proj

    def test_add_filter(self):
        proj = self._make_project_with_source()
        filt = add_filter(proj, "color_correction", 0)
        assert filt["type"] == "color_correction"
        assert filt["enabled"] is True
        assert len(proj["scenes"][0]["sources"][0]["filters"]) == 1

    def test_add_filter_with_params(self):
        proj = self._make_project_with_source()
        filt = add_filter(proj, "color_correction", 0, params={"brightness": 0.5})
        assert filt["params"]["brightness"] == 0.5

    def test_add_filter_invalid_type(self):
        proj = self._make_project_with_source()
        with pytest.raises(ValueError, match="Unknown filter type"):
            add_filter(proj, "nonexistent", 0)

    def test_add_filter_invalid_param(self):
        proj = self._make_project_with_source()
        with pytest.raises(ValueError, match="Unknown parameters"):
            add_filter(proj, "color_correction", 0, params={"bogus": 1})

    def test_add_filter_param_out_of_range(self):
        proj = self._make_project_with_source()
        with pytest.raises(ValueError, match="must be between"):
            add_filter(proj, "color_correction", 0, params={"brightness": 5.0})

    def test_add_chroma_key(self):
        proj = self._make_project_with_source()
        filt = add_filter(proj, "chroma_key", 0, params={"similarity": 500})
        assert filt["params"]["similarity"] == 500

    def test_add_noise_suppress(self):
        proj = self._make_project_with_source()
        filt = add_filter(proj, "noise_suppress", 0)
        assert filt["params"]["method"] == "rnnoise"

    def test_remove_filter(self):
        proj = self._make_project_with_source()
        add_filter(proj, "gain", 0)
        removed = remove_filter(proj, 0, 0)
        assert removed["type"] == "gain"
        assert len(proj["scenes"][0]["sources"][0]["filters"]) == 0

    def test_set_filter_param(self):
        proj = self._make_project_with_source()
        add_filter(proj, "gain", 0, params={"db": 0.0})
        set_filter_param(proj, 0, "db", 5.0, 0)
        assert proj["scenes"][0]["sources"][0]["filters"][0]["params"]["db"] == 5.0

    def test_set_filter_param_invalid(self):
        proj = self._make_project_with_source()
        add_filter(proj, "gain", 0)
        with pytest.raises(ValueError, match="Unknown parameter"):
            set_filter_param(proj, 0, "bogus", 1.0, 0)

    def test_list_filters(self):
        proj = self._make_project_with_source()
        add_filter(proj, "gain", 0)
        add_filter(proj, "compressor", 0)
        result = list_filters(proj, 0)
        assert len(result) == 2

    def test_list_available_filters(self):
        result = list_available_filters()
        assert len(result) == len(FILTER_TYPES)
        names = [f["name"] for f in result]
        assert "color_correction" in names
        assert "chroma_key" in names

    def test_list_available_filters_by_category(self):
        audio = list_available_filters(category="audio")
        assert all(f["category"] == "audio" for f in audio)
        assert len(audio) >= 4

    def test_all_filter_types_have_params(self):
        for name, spec in FILTER_TYPES.items():
            assert "params" in spec, f"Filter '{name}' missing params"
            assert "label" in spec, f"Filter '{name}' missing label"
            assert "category" in spec, f"Filter '{name}' missing category"


# -- Audio Tests -------------------------------------------------------------

class TestAudio:
    def _make_project(self):
        return create_project()

    def test_add_audio_source(self):
        proj = self._make_project()
        src = add_audio_source(proj, name="Mic")
        assert src["name"] == "Mic"
        assert src["type"] == "input"
        assert len(proj["audio_sources"]) == 1

    def test_add_audio_output(self):
        proj = self._make_project()
        src = add_audio_source(proj, name="Desktop", audio_type="output")
        assert src["type"] == "output"

    def test_add_audio_invalid_type(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Invalid audio type"):
            add_audio_source(proj, audio_type="bogus")

    def test_set_volume(self):
        proj = self._make_project()
        add_audio_source(proj)
        src = set_volume(proj, 0, 0.5)
        assert src["volume"] == 0.5

    def test_set_volume_out_of_range(self):
        proj = self._make_project()
        add_audio_source(proj)
        with pytest.raises(ValueError, match="must be between"):
            set_volume(proj, 0, 5.0)

    def test_mute(self):
        proj = self._make_project()
        add_audio_source(proj)
        src = mute(proj, 0)
        assert src["muted"] is True

    def test_unmute(self):
        proj = self._make_project()
        add_audio_source(proj, muted=True)
        src = unmute(proj, 0)
        assert src["muted"] is False

    def test_set_monitor(self):
        proj = self._make_project()
        add_audio_source(proj)
        src = set_monitor(proj, 0, "monitor_only")
        assert src["monitor"] == "monitor_only"

    def test_set_monitor_invalid(self):
        proj = self._make_project()
        add_audio_source(proj)
        with pytest.raises(ValueError, match="Invalid monitor type"):
            set_monitor(proj, 0, "bogus")

    def test_set_balance(self):
        proj = self._make_project()
        add_audio_source(proj)
        src = set_balance(proj, 0, -0.5)
        assert src["balance"] == -0.5

    def test_set_sync_offset(self):
        proj = self._make_project()
        add_audio_source(proj)
        src = set_sync_offset(proj, 0, 100)
        assert src["sync_offset"] == 100

    def test_remove_audio(self):
        proj = self._make_project()
        add_audio_source(proj, name="Mic")
        removed = remove_audio_source(proj, 0)
        assert removed["name"] == "Mic"

    def test_list_audio(self):
        proj = self._make_project()
        add_audio_source(proj, name="Mic")
        add_audio_source(proj, name="Desktop", audio_type="output")
        result = list_audio(proj)
        assert len(result) == 2

    def test_audio_unique_names(self):
        proj = self._make_project()
        a1 = add_audio_source(proj, name="Mic")
        a2 = add_audio_source(proj, name="Mic")
        assert a1["name"] != a2["name"]


# -- Transition Tests --------------------------------------------------------

class TestTransitions:
    def _make_project(self):
        return create_project()

    def test_add_transition(self):
        proj = self._make_project()
        trans = add_transition(proj, "swipe")
        assert trans["type"] == "swipe"
        assert len(proj["transitions"]) == 3

    def test_add_transition_with_duration(self):
        proj = self._make_project()
        trans = add_transition(proj, "fade", duration=500)
        assert trans["duration"] == 500

    def test_add_transition_invalid_type(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Unknown transition type"):
            add_transition(proj, "nonexistent")

    def test_add_transition_negative_duration(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="non-negative"):
            add_transition(proj, "fade", duration=-1)

    def test_remove_transition(self):
        proj = self._make_project()
        removed = remove_transition(proj, 1)
        assert removed["type"] == "fade"
        assert len(proj["transitions"]) == 1

    def test_remove_last_transition_fails(self):
        proj = self._make_project()
        remove_transition(proj, 1)
        with pytest.raises(ValueError, match="Cannot remove the last"):
            remove_transition(proj, 0)

    def test_set_duration(self):
        proj = self._make_project()
        trans = set_duration(proj, 1, 1000)
        assert trans["duration"] == 1000

    def test_set_duration_negative(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="non-negative"):
            set_duration(proj, 1, -1)

    def test_set_active_transition(self):
        proj = self._make_project()
        result = set_active_transition(proj, 1)
        assert result["index"] == 1
        assert proj["active_transition"] == 1

    def test_list_transitions(self):
        proj = self._make_project()
        result = list_transitions(proj)
        assert len(result) == 2
        assert result[0]["type"] == "cut"
        assert result[1]["type"] == "fade"

    def test_all_transition_types(self):
        proj = self._make_project()
        for ttype in TRANSITION_TYPES:
            trans = add_transition(proj, ttype)
            assert trans["type"] == ttype


# -- Output Tests ------------------------------------------------------------

class TestOutput:
    def _make_project(self):
        return create_project()

    def test_set_streaming(self):
        proj = self._make_project()
        result = set_streaming(proj, service="youtube")
        assert result["service"] == "youtube"

    def test_set_streaming_invalid_service(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Invalid streaming service"):
            set_streaming(proj, service="bogus")

    def test_set_streaming_key(self):
        proj = self._make_project()
        result = set_streaming(proj, key="abc123")
        assert result["key"] == "abc123"

    def test_set_recording(self):
        proj = self._make_project()
        result = set_recording(proj, fmt="mp4", quality="lossless")
        assert result["format"] == "mp4"
        assert result["quality"] == "lossless"

    def test_set_recording_invalid_format(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Invalid recording format"):
            set_recording(proj, fmt="avi")

    def test_set_recording_invalid_quality(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Invalid recording quality"):
            set_recording(proj, quality="ultra")

    def test_set_output_settings(self):
        proj = self._make_project()
        result = set_output_settings(proj, output_width=1280, output_height=720)
        assert result["output_width"] == 1280

    def test_set_output_settings_with_preset(self):
        proj = self._make_project()
        result = set_output_settings(proj, preset="quality")
        assert result["video_bitrate"] == 8000

    def test_set_output_settings_invalid_preset(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Unknown encoding preset"):
            set_output_settings(proj, preset="nonexistent")

    def test_set_output_settings_invalid_width(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="must be positive"):
            set_output_settings(proj, output_width=0)

    def test_set_output_settings_invalid_encoder(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Invalid encoder"):
            set_output_settings(proj, encoder="bogus")

    def test_get_output_info(self):
        proj = self._make_project()
        info = get_output_info(proj)
        assert "settings" in info
        assert "streaming" in info
        assert "recording" in info

    def test_list_encoding_presets(self):
        presets = list_encoding_presets()
        assert len(presets) == len(ENCODING_PRESETS)
        names = [p["name"] for p in presets]
        assert "balanced" in names

    def test_valid_services(self):
        assert "twitch" in VALID_SERVICES
        assert "youtube" in VALID_SERVICES

    def test_valid_formats(self):
        assert "mkv" in VALID_RECORDING_FORMATS
        assert "mp4" in VALID_RECORDING_FORMATS


# -- Session Tests -----------------------------------------------------------

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

    def test_undo_source_add(self):
        sess = Session()
        proj = create_project()
        sess.set_project(proj)

        sess.snapshot("add source")
        add_source(proj, "image", name="BG")
        assert len(proj["scenes"][0]["sources"]) == 1

        sess.undo()
        assert len(sess.get_project()["scenes"][0]["sources"]) == 0

    def test_undo_scene_add(self):
        sess = Session()
        proj = create_project()
        sess.set_project(proj)

        sess.snapshot("add scene")
        add_scene(proj, name="BRB")
        assert len(proj["scenes"]) == 2

        sess.undo()
        assert len(sess.get_project()["scenes"]) == 1
