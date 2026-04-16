"""End-to-end tests for OBS Studio CLI.

Tests complete workflows without OBS Studio installed.
"""

import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.obs_studio.core.project import create_project, save_project, open_project, get_project_info
from cli_anything.obs_studio.core.scenes import add_scene, remove_scene, duplicate_scene, set_active_scene, list_scenes
from cli_anything.obs_studio.core.sources import (
    add_source, remove_source, duplicate_source, set_source_property,
    transform_source, list_sources, SOURCE_TYPES,
)
from cli_anything.obs_studio.core.filters import add_filter, remove_filter, set_filter_param, list_filters, FILTER_TYPES
from cli_anything.obs_studio.core.audio import (
    add_audio_source, set_volume, mute, unmute, set_monitor,
    set_balance, list_audio,
)
from cli_anything.obs_studio.core.transitions import add_transition, set_duration, set_active_transition, list_transitions
from cli_anything.obs_studio.core.output import set_streaming, set_recording, set_output_settings, get_output_info
from cli_anything.obs_studio.core.session import Session


class TestStreamSetupWorkflow:
    """Test setting up a complete streaming configuration."""

    def test_full_stream_setup(self):
        # Create project
        proj = create_project(name="my_stream", output_width=1920, output_height=1080, fps=30)
        assert proj["name"] == "my_stream"

        # Add scenes
        add_scene(proj, name="Starting Soon")
        add_scene(proj, name="BRB")
        add_scene(proj, name="Ending")
        assert len(proj["scenes"]) == 4  # default + 3

        # Add sources to main scene
        cam = add_source(proj, "video_capture", scene_index=0, name="Webcam")
        assert cam["type"] == "video_capture"

        game = add_source(proj, "display_capture", scene_index=0, name="Game Capture")
        assert game["type"] == "display_capture"

        overlay = add_source(proj, "image", scene_index=0, name="Overlay",
                            settings={"file": "/path/to/overlay.png"})
        assert overlay["settings"]["file"] == "/path/to/overlay.png"

        # Add sources to BRB scene
        brb_img = add_source(proj, "image", scene_index=2, name="BRB Image")
        assert len(proj["scenes"][2]["sources"]) == 1

        # Configure streaming
        set_streaming(proj, service="twitch", server="auto", key="live_abc123")
        assert proj["streaming"]["key"] == "live_abc123"

        # Configure output
        set_output_settings(proj, preset="balanced")
        assert proj["settings"]["video_bitrate"] == 6000

        # Verify final state
        info = get_project_info(proj)
        assert info["counts"]["scenes"] == 4
        assert info["counts"]["total_sources"] == 4

    def test_camera_with_filters(self):
        proj = create_project()
        add_source(proj, "video_capture", name="Camera")

        # Add green screen setup
        add_filter(proj, "chroma_key", 0, params={"similarity": 400})
        add_filter(proj, "color_correction", 0, params={"brightness": 0.1, "contrast": 0.2})

        filters = list_filters(proj, 0)
        assert len(filters) == 2
        assert filters[0]["type"] == "chroma_key"
        assert filters[1]["type"] == "color_correction"

    def test_audio_mixer_setup(self):
        proj = create_project()

        # Add audio sources
        mic = add_audio_source(proj, name="Microphone", audio_type="input")
        desktop = add_audio_source(proj, name="Desktop Audio", audio_type="output")

        # Adjust volumes
        set_volume(proj, 0, 1.0)
        set_volume(proj, 1, 0.7)

        # Add monitoring
        set_monitor(proj, 0, "monitor_and_output")

        # Check state
        audio = list_audio(proj)
        assert len(audio) == 2
        assert audio[0]["volume"] == 1.0
        assert audio[1]["volume"] == 0.7


class TestSourceManipulation:
    """Test source manipulation workflows."""

    def test_source_layering(self):
        proj = create_project()

        # Create layered scene
        add_source(proj, "display_capture", name="Game")
        add_source(proj, "image", name="Frame Overlay",
                  position={"x": 0, "y": 0})
        add_source(proj, "video_capture", name="Webcam",
                  position={"x": 1500, "y": 800},
                  size={"width": 400, "height": 300})
        add_source(proj, "text", name="Now Playing",
                  position={"x": 10, "y": 10},
                  settings={"text": "Currently streaming!"})

        sources = list_sources(proj)
        assert len(sources) == 4
        assert sources[2]["position"]["x"] == 1500

    def test_source_transform_workflow(self):
        proj = create_project()
        add_source(proj, "video_capture", name="Camera")

        # Position and resize
        transform_source(proj, 0, position={"x": 100, "y": 100},
                         size={"width": 640, "height": 480})

        # Crop
        transform_source(proj, 0, crop={"top": 50, "bottom": 50, "left": 0, "right": 0})

        # Rotate
        transform_source(proj, 0, rotation=15.0)

        src = proj["scenes"][0]["sources"][0]
        assert src["position"]["x"] == 100
        assert src["size"]["width"] == 640
        assert src["crop"]["top"] == 50
        assert src["rotation"] == 15.0

    def test_duplicate_and_modify_source(self):
        proj = create_project()
        add_source(proj, "text", name="Alert", settings={"text": "New follower!"})
        dup = duplicate_source(proj, 0)

        # Modify the duplicate
        set_source_property(proj, 1, "visible", "false")

        assert proj["scenes"][0]["sources"][0]["visible"] is True
        assert proj["scenes"][0]["sources"][1]["visible"] is False

    def test_source_visibility_toggle(self):
        proj = create_project()
        add_source(proj, "image", name="Logo")

        set_source_property(proj, 0, "visible", "false")
        assert proj["scenes"][0]["sources"][0]["visible"] is False

        set_source_property(proj, 0, "visible", "true")
        assert proj["scenes"][0]["sources"][0]["visible"] is True


class TestSceneWorkflow:
    """Test scene management workflows."""

    def test_multi_scene_setup(self):
        proj = create_project()

        # Set up multiple scenes
        add_scene(proj, name="Gaming")
        add_scene(proj, name="Just Chatting")
        add_scene(proj, name="BRB")

        # Add sources to different scenes
        add_source(proj, "display_capture", scene_index=0, name="Desktop")
        add_source(proj, "video_capture", scene_index=1, name="Camera")
        add_source(proj, "image", scene_index=2, name="Chatting BG")
        add_source(proj, "video_capture", scene_index=2, name="Cam2")
        add_source(proj, "image", scene_index=3, name="BRB Screen")

        scenes = list_scenes(proj)
        assert len(scenes) == 4
        assert scenes[0]["source_count"] == 1
        assert scenes[2]["source_count"] == 2

    def test_scene_switching(self):
        proj = create_project()
        add_scene(proj, name="BRB")

        assert proj["active_scene"] == 0
        set_active_scene(proj, 1)
        assert proj["active_scene"] == 1

    def test_duplicate_scene_with_sources(self):
        proj = create_project()
        add_source(proj, "image", scene_index=0, name="BG")
        add_source(proj, "text", scene_index=0, name="Title")

        dup = duplicate_scene(proj, 0)
        assert len(dup["sources"]) == 2
        # Sources should be independent copies
        dup["sources"][0]["name"] = "Modified"
        assert proj["scenes"][0]["sources"][0]["name"] == "BG"

    def test_remove_scene_keeps_others(self):
        proj = create_project()
        add_scene(proj, name="A")
        add_scene(proj, name="B")
        assert len(proj["scenes"]) == 3

        remove_scene(proj, 1)
        assert len(proj["scenes"]) == 2
        assert proj["scenes"][1]["name"] == "B"


class TestFilterChains:
    """Test filter chain workflows."""

    def test_audio_filter_chain(self):
        proj = create_project()
        add_source(proj, "audio_input", name="Mic")

        add_filter(proj, "noise_suppress", 0, params={"method": "rnnoise"})
        add_filter(proj, "noise_gate", 0, params={"open_threshold": -26.0})
        add_filter(proj, "compressor", 0, params={"ratio": 10.0, "threshold": -18.0})
        add_filter(proj, "gain", 0, params={"db": 3.0})
        add_filter(proj, "limiter", 0, params={"threshold": -3.0})

        filters = list_filters(proj, 0)
        assert len(filters) == 5
        assert filters[0]["type"] == "noise_suppress"
        assert filters[4]["type"] == "limiter"

    def test_video_filter_chain(self):
        proj = create_project()
        add_source(proj, "video_capture", name="Camera")

        add_filter(proj, "chroma_key", 0, params={"key_color_type": "green"})
        add_filter(proj, "color_correction", 0, params={"saturation": 1.5})
        add_filter(proj, "sharpen", 0, params={"sharpness": 0.1})

        filters = list_filters(proj, 0)
        assert len(filters) == 3

    def test_modify_filter_in_chain(self):
        proj = create_project()
        add_source(proj, "video_capture", name="Camera")
        add_filter(proj, "color_correction", 0, params={"brightness": 0.0})

        set_filter_param(proj, 0, "brightness", 0.3, 0)
        assert proj["scenes"][0]["sources"][0]["filters"][0]["params"]["brightness"] == 0.3

    def test_remove_filter_from_chain(self):
        proj = create_project()
        add_source(proj, "audio_input", name="Mic")
        add_filter(proj, "gain", 0)
        add_filter(proj, "compressor", 0)
        add_filter(proj, "limiter", 0)

        remove_filter(proj, 1, 0)  # remove compressor
        filters = list_filters(proj, 0)
        assert len(filters) == 2
        assert filters[0]["type"] == "gain"
        assert filters[1]["type"] == "limiter"


class TestTransitionWorkflow:
    """Test transition workflows."""

    def test_transition_setup(self):
        proj = create_project()

        add_transition(proj, "stinger", name="My Stinger", duration=1500)
        add_transition(proj, "slide", duration=700)

        transitions = list_transitions(proj)
        assert len(transitions) == 4  # 2 default + 2 added

    def test_transition_duration_change(self):
        proj = create_project()
        set_duration(proj, 1, 500)  # Change Fade duration
        assert proj["transitions"][1]["duration"] == 500


class TestOutputConfiguration:
    """Test output configuration workflows."""

    def test_full_output_config(self):
        proj = create_project()

        # Configure streaming
        set_streaming(proj, service="youtube", server="auto", key="stream_key_here")

        # Configure recording
        set_recording(proj, path="/recordings/", fmt="mp4", quality="high")

        # Configure encoding
        set_output_settings(proj, output_width=1920, output_height=1080,
                           fps=60, video_bitrate=8000)

        info = get_output_info(proj)
        assert info["streaming"]["service"] == "youtube"
        assert info["recording"]["format"] == "mp4"
        assert info["settings"]["fps"] == 60

    def test_preset_then_override(self):
        proj = create_project()
        set_output_settings(proj, preset="quality")
        assert proj["settings"]["video_bitrate"] == 8000

        # Override single setting
        set_output_settings(proj, video_bitrate=10000)
        assert proj["settings"]["video_bitrate"] == 10000
        # Encoder should still be from preset
        assert proj["settings"]["encoder"] == "x264"


class TestSaveLoadRoundtrip:
    """Test save/load roundtrips."""

    def test_full_roundtrip(self):
        proj = create_project(name="roundtrip_test")
        add_scene(proj, name="Extra")
        add_source(proj, "video_capture", scene_index=0, name="Camera")
        add_source(proj, "image", scene_index=1, name="BG")
        add_filter(proj, "chroma_key", 0, scene_index=0)
        add_audio_source(proj, name="Mic")
        add_transition(proj, "fade", duration=500)
        set_streaming(proj, service="youtube")
        set_recording(proj, fmt="mp4")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_project(proj, path)
            loaded = open_project(path)

            assert loaded["name"] == "roundtrip_test"
            assert len(loaded["scenes"]) == 2
            assert len(loaded["scenes"][0]["sources"]) == 1
            assert len(loaded["scenes"][0]["sources"][0]["filters"]) == 1
            assert len(loaded["audio_sources"]) == 1
            assert len(loaded["transitions"]) == 3
            assert loaded["streaming"]["service"] == "youtube"
            assert loaded["recording"]["format"] == "mp4"
        finally:
            os.unlink(path)

    def test_save_load_preserves_source_transforms(self):
        proj = create_project()
        add_source(proj, "image", name="Logo", position={"x": 100, "y": 200},
                  size={"width": 300, "height": 300})
        transform_source(proj, 0, crop={"top": 10, "bottom": 10, "left": 5, "right": 5})

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_project(proj, path)
            loaded = open_project(path)
            src = loaded["scenes"][0]["sources"][0]
            assert src["position"]["x"] == 100
            assert src["size"]["width"] == 300
            assert src["crop"]["top"] == 10
        finally:
            os.unlink(path)


class TestSessionUndoRedo:
    """Test session undo/redo in realistic workflows."""

    def test_undo_add_source(self):
        sess = Session()
        proj = create_project()
        sess.set_project(proj)

        sess.snapshot("add camera")
        add_source(proj, "video_capture", name="Camera")
        assert len(proj["scenes"][0]["sources"]) == 1

        sess.undo()
        assert len(sess.get_project()["scenes"][0]["sources"]) == 0

        sess.redo()
        assert len(sess.get_project()["scenes"][0]["sources"]) == 1

    def test_undo_add_scene(self):
        sess = Session()
        proj = create_project()
        sess.set_project(proj)

        sess.snapshot("add scene")
        add_scene(proj, name="BRB")
        assert len(proj["scenes"]) == 2

        sess.undo()
        assert len(sess.get_project()["scenes"]) == 1

    def test_undo_filter_chain(self):
        sess = Session()
        proj = create_project()
        add_source(proj, "video_capture", name="Camera")
        sess.set_project(proj)

        sess.snapshot("add filter")
        add_filter(proj, "chroma_key", 0)
        assert len(proj["scenes"][0]["sources"][0]["filters"]) == 1

        sess.snapshot("add filter 2")
        add_filter(proj, "color_correction", 0)
        assert len(proj["scenes"][0]["sources"][0]["filters"]) == 2

        sess.undo()
        assert len(sess.get_project()["scenes"][0]["sources"][0]["filters"]) == 1

        sess.undo()
        assert len(sess.get_project()["scenes"][0]["sources"][0]["filters"]) == 0

    def test_undo_audio_changes(self):
        sess = Session()
        proj = create_project()
        add_audio_source(proj, name="Mic", volume=1.0)
        sess.set_project(proj)

        sess.snapshot("change volume")
        set_volume(proj, 0, 0.5)
        assert proj["audio_sources"][0]["volume"] == 0.5

        sess.undo()
        assert sess.get_project()["audio_sources"][0]["volume"] == 1.0

    def test_multiple_undo_redo(self):
        sess = Session()
        proj = create_project(name="v1")
        sess.set_project(proj)

        sess.snapshot("rename to v2")
        proj["name"] = "v2"

        sess.snapshot("rename to v3")
        proj["name"] = "v3"

        sess.snapshot("rename to v4")
        proj["name"] = "v4"

        sess.undo()
        assert sess.get_project()["name"] == "v3"
        sess.undo()
        assert sess.get_project()["name"] == "v2"
        sess.undo()
        assert sess.get_project()["name"] == "v1"

        sess.redo()
        assert sess.get_project()["name"] == "v2"
        sess.redo()
        assert sess.get_project()["name"] == "v3"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_project_info(self):
        proj = create_project()
        info = get_project_info(proj)
        assert info["counts"]["total_sources"] == 0

    def test_source_on_nonexistent_scene(self):
        proj = create_project()
        with pytest.raises(IndexError):
            add_source(proj, "image", scene_index=99)

    def test_filter_on_nonexistent_source(self):
        proj = create_project()
        with pytest.raises(ValueError):
            add_filter(proj, "gain", source_index=99)

    def test_remove_source_empty_scene(self):
        proj = create_project()
        with pytest.raises(ValueError):
            remove_source(proj, 0)

    def test_transform_nonexistent_source(self):
        proj = create_project()
        with pytest.raises(ValueError):
            transform_source(proj, 0, position={"x": 0, "y": 0})

    def test_negative_crop(self):
        proj = create_project()
        add_source(proj, "image")
        with pytest.raises(ValueError, match="non-negative"):
            transform_source(proj, 0, crop={"top": -1})

    def test_all_source_types_addable(self):
        proj = create_project()
        for stype in SOURCE_TYPES:
            src = add_source(proj, stype)
            assert src is not None
        assert len(proj["scenes"][0]["sources"]) == len(SOURCE_TYPES)

    def test_all_filter_types_addable(self):
        proj = create_project()
        add_source(proj, "video_capture", name="Camera")
        for ftype in FILTER_TYPES:
            filt = add_filter(proj, ftype, 0)
            assert filt is not None
        assert len(proj["scenes"][0]["sources"][0]["filters"]) == len(FILTER_TYPES)

    def test_chroma_key_invalid_color_type(self):
        proj = create_project()
        add_source(proj, "video_capture")
        with pytest.raises(ValueError):
            add_filter(proj, "chroma_key", 0, params={"key_color_type": "red"})

    def test_session_save_no_path(self):
        sess = Session()
        proj = create_project()
        sess.set_project(proj)
        with pytest.raises(ValueError, match="No save path"):
            sess.save_session()

    def test_large_scene_collection(self):
        proj = create_project()
        for i in range(20):
            add_scene(proj, name=f"Scene {i}")
        assert len(proj["scenes"]) == 21
        for i in range(21):
            add_source(proj, "text", scene_index=i, name=f"Text {i}")
        info = get_project_info(proj)
        assert info["counts"]["total_sources"] == 21
