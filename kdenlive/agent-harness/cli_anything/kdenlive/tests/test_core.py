"""Unit tests for Kdenlive CLI core modules.

Tests use synthetic data only -- no Kdenlive or melt installation required.
"""

import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.kdenlive.core.project import (
    create_project, open_project, save_project, get_project_info,
    list_profiles, PROFILES, PROJECT_VERSION,
)
from cli_anything.kdenlive.core.bin import (
    import_clip, remove_clip, list_clips, get_clip, CLIP_TYPES,
)
from cli_anything.kdenlive.core.timeline import (
    add_track, remove_track, add_clip_to_track, remove_clip_from_track,
    trim_clip, split_clip, move_clip, list_tracks, TRACK_TYPES,
)
from cli_anything.kdenlive.core.filters import (
    FILTER_REGISTRY, add_filter, remove_filter, set_filter_param,
    list_filters, list_available,
)
from cli_anything.kdenlive.core.transitions import (
    add_transition, remove_transition, set_transition, list_transitions,
    TRANSITION_TYPES,
)
from cli_anything.kdenlive.core.guides import (
    add_guide, remove_guide, list_guides, GUIDE_TYPES,
)
from cli_anything.kdenlive.core.export import (
    generate_kdenlive_xml, list_render_presets, RENDER_PRESETS,
)
from cli_anything.kdenlive.core.session import Session
from cli_anything.kdenlive.utils.mlt_xml import (
    seconds_to_timecode, timecode_to_seconds, seconds_to_frames,
    frames_to_seconds, xml_escape,
)


# ── Project Tests ───────────────────────────────────────────────

class TestProject:
    def test_create_default(self):
        proj = create_project()
        assert proj["version"] == PROJECT_VERSION
        assert proj["profile"]["width"] == 1920
        assert proj["profile"]["height"] == 1080
        assert proj["profile"]["fps_num"] == 30
        assert proj["profile"]["fps_den"] == 1

    def test_create_with_name(self):
        proj = create_project(name="MyVideo")
        assert proj["name"] == "MyVideo"

    def test_create_with_profile(self):
        proj = create_project(profile="hd720p30")
        assert proj["profile"]["width"] == 1280
        assert proj["profile"]["height"] == 720
        assert proj["profile"]["fps_num"] == 30

    def test_create_4k_profile(self):
        proj = create_project(profile="4k30")
        assert proj["profile"]["width"] == 3840
        assert proj["profile"]["height"] == 2160

    def test_create_sd_pal_profile(self):
        proj = create_project(profile="sd_pal")
        assert proj["profile"]["width"] == 720
        assert proj["profile"]["height"] == 576
        assert proj["profile"]["progressive"] is False

    def test_create_invalid_profile(self):
        with pytest.raises(ValueError, match="Unknown profile"):
            create_project(profile="nonexistent")

    def test_create_invalid_resolution(self):
        with pytest.raises(ValueError, match="must be positive"):
            create_project(width=0, height=100)

    def test_create_invalid_fps(self):
        with pytest.raises(ValueError, match="must be positive"):
            create_project(fps_num=0)

    def test_create_custom_dimensions(self):
        proj = create_project(width=800, height=600, fps_num=25, fps_den=1)
        assert proj["profile"]["width"] == 800
        assert proj["profile"]["height"] == 600
        assert proj["profile"]["fps_num"] == 25

    def test_create_has_empty_collections(self):
        proj = create_project()
        assert proj["bin"] == []
        assert proj["tracks"] == []
        assert proj["transitions"] == []
        assert proj["guides"] == []

    def test_create_has_metadata(self):
        proj = create_project()
        assert "created" in proj["metadata"]
        assert "software" in proj["metadata"]

    def test_save_and_open(self):
        proj = create_project(name="test_proj")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_project(proj, path)
            loaded = open_project(path)
            assert loaded["name"] == "test_proj"
            assert loaded["profile"]["width"] == 1920
        finally:
            os.unlink(path)

    def test_open_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            open_project("/nonexistent/path.json")

    def test_open_invalid_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump({"invalid": True}, f)
            path = f.name
        try:
            with pytest.raises(ValueError, match="Invalid project file"):
                open_project(path)
        finally:
            os.unlink(path)

    def test_get_project_info(self):
        proj = create_project(name="info_test")
        info = get_project_info(proj)
        assert info["name"] == "info_test"
        assert info["counts"]["bin_clips"] == 0
        assert "profile" in info

    def test_list_profiles(self):
        profiles = list_profiles()
        assert len(profiles) == len(PROFILES)
        names = [p["name"] for p in profiles]
        assert "hd1080p30" in names
        assert "4k30" in names
        assert "sd_pal" in names

    def test_all_profiles_valid(self):
        for name in PROFILES:
            proj = create_project(profile=name)
            assert proj["profile"]["width"] > 0
            assert proj["profile"]["height"] > 0


# ── Bin Tests ───────────────────────────────────────────────────

class TestBin:
    def _make_project(self):
        return create_project()

    def test_import_clip(self):
        proj = self._make_project()
        clip = import_clip(proj, "/path/to/video.mp4", name="Interview", duration=120.5)
        assert clip["name"] == "Interview"
        assert clip["source"] == "/path/to/video.mp4"
        assert clip["duration"] == 120.5
        assert clip["type"] == "video"
        assert len(proj["bin"]) == 1

    def test_import_clip_auto_name(self):
        proj = self._make_project()
        clip = import_clip(proj, "/path/to/my_video.mp4")
        assert clip["name"] == "my_video"

    def test_import_clip_types(self):
        proj = self._make_project()
        for ct in CLIP_TYPES:
            clip = import_clip(proj, f"/path/{ct}.file", clip_type=ct)
            assert clip["type"] == ct

    def test_import_clip_invalid_type(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Invalid clip type"):
            import_clip(proj, "/path/file.mp4", clip_type="invalid")

    def test_import_clip_negative_duration(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="non-negative"):
            import_clip(proj, "/path/file.mp4", duration=-1.0)

    def test_unique_clip_ids(self):
        proj = self._make_project()
        c1 = import_clip(proj, "/a.mp4")
        c2 = import_clip(proj, "/b.mp4")
        assert c1["id"] != c2["id"]

    def test_unique_clip_names(self):
        proj = self._make_project()
        c1 = import_clip(proj, "/a.mp4", name="Clip")
        c2 = import_clip(proj, "/b.mp4", name="Clip")
        assert c1["name"] != c2["name"]

    def test_remove_clip(self):
        proj = self._make_project()
        clip = import_clip(proj, "/a.mp4", name="Test")
        removed = remove_clip(proj, clip["id"])
        assert removed["name"] == "Test"
        assert len(proj["bin"]) == 0

    def test_remove_clip_not_found(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Clip not found"):
            remove_clip(proj, "nonexistent")

    def test_list_clips(self):
        proj = self._make_project()
        import_clip(proj, "/a.mp4", name="A")
        import_clip(proj, "/b.mp4", name="B")
        clips = list_clips(proj)
        assert len(clips) == 2

    def test_get_clip(self):
        proj = self._make_project()
        clip = import_clip(proj, "/a.mp4", name="Test")
        fetched = get_clip(proj, clip["id"])
        assert fetched["name"] == "Test"

    def test_get_clip_not_found(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Clip not found"):
            get_clip(proj, "nonexistent")


# ── Timeline Tests ──────────────────────────────────────────────

class TestTimeline:
    def _make_project_with_clip(self):
        proj = create_project()
        import_clip(proj, "/video.mp4", name="TestClip", duration=30.0)
        return proj

    def test_add_video_track(self):
        proj = self._make_project_with_clip()
        track = add_track(proj, track_type="video")
        assert track["type"] == "video"
        assert track["name"] == "V1"
        assert len(proj["tracks"]) == 1

    def test_add_audio_track(self):
        proj = self._make_project_with_clip()
        track = add_track(proj, track_type="audio")
        assert track["type"] == "audio"
        assert track["name"] == "A1"

    def test_add_track_custom_name(self):
        proj = self._make_project_with_clip()
        track = add_track(proj, name="MyTrack")
        assert track["name"] == "MyTrack"

    def test_add_track_invalid_type(self):
        proj = self._make_project_with_clip()
        with pytest.raises(ValueError, match="Invalid track type"):
            add_track(proj, track_type="invalid")

    def test_remove_track(self):
        proj = self._make_project_with_clip()
        track = add_track(proj)
        removed = remove_track(proj, track["id"])
        assert removed["name"] == track["name"]
        assert len(proj["tracks"]) == 0

    def test_remove_track_not_found(self):
        proj = self._make_project_with_clip()
        with pytest.raises(ValueError, match="Track not found"):
            remove_track(proj, 999)

    def test_add_clip_to_track(self):
        proj = self._make_project_with_clip()
        track = add_track(proj)
        entry = add_clip_to_track(proj, track["id"], "clip0", position=0.0,
                                   in_point=0.0, out_point=10.0)
        assert entry["clip_id"] == "clip0"
        assert entry["position"] == 0.0
        assert entry["in"] == 0.0
        assert entry["out"] == 10.0

    def test_add_clip_to_track_auto_out(self):
        proj = self._make_project_with_clip()
        track = add_track(proj)
        entry = add_clip_to_track(proj, track["id"], "clip0")
        assert entry["out"] == 30.0  # full clip duration

    def test_add_clip_invalid_clip_id(self):
        proj = self._make_project_with_clip()
        track = add_track(proj)
        with pytest.raises(ValueError, match="Clip not found"):
            add_clip_to_track(proj, track["id"], "nonexistent")

    def test_add_clip_locked_track(self):
        proj = self._make_project_with_clip()
        track = add_track(proj, locked=True)
        with pytest.raises(RuntimeError, match="locked"):
            add_clip_to_track(proj, track["id"], "clip0")

    def test_add_clip_invalid_in_out(self):
        proj = self._make_project_with_clip()
        track = add_track(proj)
        with pytest.raises(ValueError, match="greater than in-point"):
            add_clip_to_track(proj, track["id"], "clip0", in_point=10.0, out_point=5.0)

    def test_remove_clip_from_track(self):
        proj = self._make_project_with_clip()
        track = add_track(proj)
        add_clip_to_track(proj, track["id"], "clip0", out_point=10.0)
        removed = remove_clip_from_track(proj, track["id"], 0)
        assert removed["clip_id"] == "clip0"
        assert len(proj["tracks"][0]["clips"]) == 0

    def test_remove_clip_from_track_empty(self):
        proj = self._make_project_with_clip()
        track = add_track(proj)
        with pytest.raises(ValueError, match="No clips"):
            remove_clip_from_track(proj, track["id"], 0)

    def test_trim_clip(self):
        proj = self._make_project_with_clip()
        track = add_track(proj)
        add_clip_to_track(proj, track["id"], "clip0", out_point=20.0)
        result = trim_clip(proj, track["id"], 0, new_in=5.0, new_out=15.0)
        assert result["in"] == 5.0
        assert result["out"] == 15.0

    def test_trim_clip_invalid(self):
        proj = self._make_project_with_clip()
        track = add_track(proj)
        add_clip_to_track(proj, track["id"], "clip0", out_point=20.0)
        with pytest.raises(ValueError, match="greater than in-point"):
            trim_clip(proj, track["id"], 0, new_in=20.0, new_out=5.0)

    def test_split_clip(self):
        proj = self._make_project_with_clip()
        track = add_track(proj)
        add_clip_to_track(proj, track["id"], "clip0", out_point=20.0)
        parts = split_clip(proj, track["id"], 0, split_at=10.0)
        assert len(parts) == 2
        assert parts[0]["out"] == 10.0
        assert parts[1]["in"] == 10.0
        assert len(proj["tracks"][0]["clips"]) == 2

    def test_split_clip_at_boundary(self):
        proj = self._make_project_with_clip()
        track = add_track(proj)
        add_clip_to_track(proj, track["id"], "clip0", out_point=20.0)
        with pytest.raises(ValueError, match="Split point"):
            split_clip(proj, track["id"], 0, split_at=0.0)

    def test_split_clip_beyond_duration(self):
        proj = self._make_project_with_clip()
        track = add_track(proj)
        add_clip_to_track(proj, track["id"], "clip0", out_point=20.0)
        with pytest.raises(ValueError, match="Split point"):
            split_clip(proj, track["id"], 0, split_at=25.0)

    def test_move_clip(self):
        proj = self._make_project_with_clip()
        track = add_track(proj)
        add_clip_to_track(proj, track["id"], "clip0", position=0.0, out_point=10.0)
        result = move_clip(proj, track["id"], 0, new_position=5.0)
        assert result["position"] == 5.0

    def test_move_clip_negative(self):
        proj = self._make_project_with_clip()
        track = add_track(proj)
        add_clip_to_track(proj, track["id"], "clip0", out_point=10.0)
        with pytest.raises(ValueError, match="non-negative"):
            move_clip(proj, track["id"], 0, new_position=-1.0)

    def test_list_tracks(self):
        proj = self._make_project_with_clip()
        add_track(proj, track_type="video")
        add_track(proj, track_type="audio")
        tracks = list_tracks(proj)
        assert len(tracks) == 2

    def test_clips_sorted_by_position(self):
        proj = self._make_project_with_clip()
        track = add_track(proj)
        add_clip_to_track(proj, track["id"], "clip0", position=10.0, out_point=15.0)
        add_clip_to_track(proj, track["id"], "clip0", position=0.0, out_point=5.0)
        clips = proj["tracks"][0]["clips"]
        assert clips[0]["position"] <= clips[1]["position"]


# ── Filter Tests ────────────────────────────────────────────────

class TestFilters:
    def _make_project_with_clip_on_track(self):
        proj = create_project()
        import_clip(proj, "/video.mp4", name="Test", duration=30.0)
        add_track(proj, track_type="video")
        add_clip_to_track(proj, 0, "clip0", out_point=30.0)
        return proj

    def test_add_filter(self):
        proj = self._make_project_with_clip_on_track()
        f = add_filter(proj, 0, 0, "brightness", {"level": 1.5})
        assert f["name"] == "brightness"
        assert f["params"]["level"] == 1.5
        assert f["mlt_service"] == "brightness"

    def test_add_filter_defaults(self):
        proj = self._make_project_with_clip_on_track()
        f = add_filter(proj, 0, 0, "blur")
        assert f["params"]["hblur"] == 2
        assert f["params"]["vblur"] == 2

    def test_add_filter_unknown(self):
        proj = self._make_project_with_clip_on_track()
        with pytest.raises(ValueError, match="Unknown filter"):
            add_filter(proj, 0, 0, "nonexistent")

    def test_add_filter_invalid_param(self):
        proj = self._make_project_with_clip_on_track()
        with pytest.raises(ValueError, match="Unknown parameters"):
            add_filter(proj, 0, 0, "brightness", {"bogus": 1})

    def test_add_filter_out_of_range(self):
        proj = self._make_project_with_clip_on_track()
        with pytest.raises(ValueError, match="out of range"):
            add_filter(proj, 0, 0, "brightness", {"level": 99.0})

    def test_remove_filter(self):
        proj = self._make_project_with_clip_on_track()
        add_filter(proj, 0, 0, "brightness")
        removed = remove_filter(proj, 0, 0, 0)
        assert removed["name"] == "brightness"
        assert len(proj["tracks"][0]["clips"][0]["filters"]) == 0

    def test_remove_filter_invalid_index(self):
        proj = self._make_project_with_clip_on_track()
        with pytest.raises(IndexError):
            remove_filter(proj, 0, 0, 0)

    def test_set_filter_param(self):
        proj = self._make_project_with_clip_on_track()
        add_filter(proj, 0, 0, "brightness")
        result = set_filter_param(proj, 0, 0, 0, "level", 2.0)
        assert result["params"]["level"] == 2.0

    def test_set_filter_param_invalid(self):
        proj = self._make_project_with_clip_on_track()
        add_filter(proj, 0, 0, "brightness")
        with pytest.raises(ValueError, match="Unknown parameter"):
            set_filter_param(proj, 0, 0, 0, "bogus", 1.0)

    def test_list_filters(self):
        proj = self._make_project_with_clip_on_track()
        add_filter(proj, 0, 0, "brightness")
        add_filter(proj, 0, 0, "contrast")
        filters = list_filters(proj, 0, 0)
        assert len(filters) == 2

    def test_list_available_all(self):
        avail = list_available()
        assert len(avail) == len(FILTER_REGISTRY)
        names = [f["name"] for f in avail]
        assert "brightness" in names
        assert "chroma_key" in names

    def test_list_available_by_category(self):
        avail = list_available(category="color")
        assert all(f["category"] == "color" for f in avail)

    def test_all_filters_have_mlt_service(self):
        for name, spec in FILTER_REGISTRY.items():
            assert "mlt_service" in spec, f"Filter '{name}' missing mlt_service"
            assert spec["mlt_service"], f"Filter '{name}' has empty mlt_service"

    def test_chroma_key_filter(self):
        proj = self._make_project_with_clip_on_track()
        f = add_filter(proj, 0, 0, "chroma_key", {"color": "#00ff00", "variance": 0.2})
        assert f["params"]["color"] == "#00ff00"
        assert f["params"]["variance"] == 0.2

    def test_volume_filter(self):
        proj = self._make_project_with_clip_on_track()
        f = add_filter(proj, 0, 0, "volume", {"gain": 0.5})
        assert f["params"]["gain"] == 0.5

    def test_speed_filter(self):
        proj = self._make_project_with_clip_on_track()
        f = add_filter(proj, 0, 0, "speed", {"speed": 2.0})
        assert f["params"]["speed"] == 2.0


# ── Transition Tests ────────────────────────────────────────────

class TestTransitions:
    def _make_project_with_tracks(self):
        proj = create_project()
        add_track(proj, track_type="video")
        add_track(proj, track_type="video")
        return proj

    def test_add_dissolve(self):
        proj = self._make_project_with_tracks()
        t = add_transition(proj, "dissolve", 0, 1, position=5.0, duration=1.0)
        assert t["type"] == "dissolve"
        assert t["track_a"] == 0
        assert t["track_b"] == 1

    def test_add_transition_unknown(self):
        proj = self._make_project_with_tracks()
        with pytest.raises(ValueError, match="Unknown transition type"):
            add_transition(proj, "nonexistent", 0, 1)

    def test_add_transition_same_track(self):
        proj = self._make_project_with_tracks()
        with pytest.raises(ValueError, match="different tracks"):
            add_transition(proj, "dissolve", 0, 0)

    def test_add_transition_invalid_track(self):
        proj = self._make_project_with_tracks()
        with pytest.raises(ValueError, match="Track not found"):
            add_transition(proj, "dissolve", 0, 99)

    def test_remove_transition(self):
        proj = self._make_project_with_tracks()
        t = add_transition(proj, "dissolve", 0, 1)
        removed = remove_transition(proj, t["id"])
        assert removed["type"] == "dissolve"
        assert len(proj["transitions"]) == 0

    def test_remove_transition_not_found(self):
        proj = self._make_project_with_tracks()
        with pytest.raises(ValueError, match="Transition not found"):
            remove_transition(proj, 999)

    def test_set_transition_param(self):
        proj = self._make_project_with_tracks()
        t = add_transition(proj, "dissolve", 0, 1)
        result = set_transition(proj, t["id"], "softness", 0.5)
        assert result["params"]["softness"] == 0.5

    def test_set_transition_position(self):
        proj = self._make_project_with_tracks()
        t = add_transition(proj, "dissolve", 0, 1)
        result = set_transition(proj, t["id"], "position", 10.0)
        assert result["position"] == 10.0

    def test_set_transition_duration(self):
        proj = self._make_project_with_tracks()
        t = add_transition(proj, "dissolve", 0, 1)
        result = set_transition(proj, t["id"], "duration", 2.5)
        assert result["duration"] == 2.5

    def test_list_transitions(self):
        proj = self._make_project_with_tracks()
        add_transition(proj, "dissolve", 0, 1)
        add_transition(proj, "wipe", 0, 1, position=10.0)
        transitions = list_transitions(proj)
        assert len(transitions) == 2

    def test_all_transition_types_have_mlt_service(self):
        for name, spec in TRANSITION_TYPES.items():
            assert "mlt_service" in spec
            assert spec["mlt_service"]


# ── Guide Tests ─────────────────────────────────────────────────

class TestGuides:
    def _make_project(self):
        return create_project()

    def test_add_guide(self):
        proj = self._make_project()
        g = add_guide(proj, 10.0, label="Intro")
        assert g["position"] == 10.0
        assert g["label"] == "Intro"

    def test_add_guide_types(self):
        proj = self._make_project()
        for gt in GUIDE_TYPES:
            g = add_guide(proj, 1.0, guide_type=gt)
            assert g["type"] == gt

    def test_add_guide_invalid_type(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Invalid guide type"):
            add_guide(proj, 1.0, guide_type="invalid")

    def test_add_guide_negative_position(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="non-negative"):
            add_guide(proj, -1.0)

    def test_guides_sorted_by_position(self):
        proj = self._make_project()
        add_guide(proj, 20.0, label="B")
        add_guide(proj, 5.0, label="A")
        guides = proj["guides"]
        assert guides[0]["position"] <= guides[1]["position"]

    def test_remove_guide(self):
        proj = self._make_project()
        g = add_guide(proj, 10.0)
        removed = remove_guide(proj, g["id"])
        assert removed["position"] == 10.0
        assert len(proj["guides"]) == 0

    def test_remove_guide_not_found(self):
        proj = self._make_project()
        with pytest.raises(ValueError, match="Guide not found"):
            remove_guide(proj, 999)

    def test_list_guides(self):
        proj = self._make_project()
        add_guide(proj, 5.0, label="A")
        add_guide(proj, 10.0, label="B")
        guides = list_guides(proj)
        assert len(guides) == 2


# ── Timecode / MLT XML Utility Tests ────────────────────────────

class TestTimecodeUtils:
    def test_seconds_to_timecode_zero(self):
        assert seconds_to_timecode(0) == "00:00:00.000"

    def test_seconds_to_timecode_simple(self):
        assert seconds_to_timecode(65.5) == "00:01:05.500"

    def test_seconds_to_timecode_hours(self):
        assert seconds_to_timecode(3661.123) == "01:01:01.123"

    def test_seconds_to_timecode_negative(self):
        with pytest.raises(ValueError, match="non-negative"):
            seconds_to_timecode(-1.0)

    def test_timecode_to_seconds_simple(self):
        assert timecode_to_seconds("00:01:05.500") == 65.5

    def test_timecode_to_seconds_hours(self):
        result = timecode_to_seconds("01:01:01.123")
        assert abs(result - 3661.123) < 0.001

    def test_timecode_to_seconds_plain_float(self):
        assert timecode_to_seconds("30.5") == 30.5

    def test_timecode_to_seconds_invalid(self):
        with pytest.raises(ValueError, match="Invalid timecode"):
            timecode_to_seconds("invalid")

    def test_roundtrip_timecode(self):
        for val in [0.0, 1.5, 60.0, 3600.0, 7261.789]:
            tc = seconds_to_timecode(val)
            back = timecode_to_seconds(tc)
            assert abs(back - val) < 0.002

    def test_seconds_to_frames(self):
        assert seconds_to_frames(1.0, 30, 1) == 30
        assert seconds_to_frames(2.0, 25, 1) == 50

    def test_frames_to_seconds(self):
        assert frames_to_seconds(30, 30, 1) == 1.0
        assert frames_to_seconds(50, 25, 1) == 2.0

    def test_xml_escape(self):
        assert xml_escape('a<b>c&d"e') == 'a&lt;b&gt;c&amp;d&quot;e'

    def test_xml_escape_apostrophe(self):
        assert xml_escape("it's") == "it&apos;s"


# ── Session Tests ───────────────────────────────────────────────

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

    def test_undo_import_clip(self):
        sess = Session()
        proj = create_project()
        sess.set_project(proj)

        sess.snapshot("import clip")
        import_clip(proj, "/a.mp4", name="Test", duration=10.0)
        assert len(proj["bin"]) == 1

        sess.undo()
        assert len(sess.get_project()["bin"]) == 0
