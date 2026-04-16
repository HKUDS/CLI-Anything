#!/usr/bin/env python3
"""Comprehensive end-to-end tests using a real video file (1.mp4).

Covers every CLI function and complex multi-step editing workflows
that reproduce real-world video editing scenarios.
"""

import os
import sys
import json
import copy
import tempfile
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.shotcut.core.session import Session
from cli_anything.shotcut.core import project as proj_mod
from cli_anything.shotcut.core import timeline as tl_mod
from cli_anything.shotcut.core import filters as filt_mod
from cli_anything.shotcut.core import media as media_mod
from cli_anything.shotcut.core import export as export_mod
from cli_anything.shotcut.utils.time import (
    timecode_to_frames, frames_to_timecode, parse_time_input,
    frames_to_seconds, seconds_to_frames, format_duration,
)
from cli_anything.shotcut.utils.mlt_xml import (
    mlt_to_string, parse_mlt, write_mlt, get_property, set_property,
    get_main_tractor, get_tractor_tracks, get_all_producers, get_all_filters,
    get_playlist_entries, find_element_by_id, create_producer, add_filter_to_element,
    remove_property, deep_copy_element, new_id,
)

VIDEO = "/root/shotcut/1.mp4"


@pytest.fixture
def video():
    """Ensure the test video exists."""
    assert os.path.isfile(VIDEO), f"Test video not found: {VIDEO}"
    return VIDEO


@pytest.fixture
def session():
    """Fresh session with a new HD project."""
    s = Session()
    proj_mod.new_project(s, "hd1080p30")
    return s


@pytest.fixture
def session_with_tracks(session):
    """Session with V1, V2, A1 tracks already added."""
    tl_mod.add_track(session, "video", "V1")
    tl_mod.add_track(session, "video", "V2")
    tl_mod.add_track(session, "audio", "A1")
    return session


# ============================================================================
# 1. PROJECT MANAGEMENT — full lifecycle
# ============================================================================

class TestProjectLifecycle:
    """Test every project command."""

    def test_new_all_profiles(self):
        """Create a project with every available profile."""
        profiles = proj_mod.list_profiles()
        for name in profiles:
            s = Session()
            result = proj_mod.new_project(s, name)
            assert result["profile"] == name
            assert s.is_open
            info = proj_mod.project_info(s)
            assert info["profile"]["width"] == profiles[name]["resolution"].split("x")[0]

    def test_save_open_roundtrip(self, session, video):
        """Create project, add content, save, reopen, verify everything."""
        tl_mod.add_track(session, "video", "Main")
        tl_mod.add_track(session, "audio", "BGM")
        tl_mod.add_clip(session, video, 1,
                        in_point="00:00:00.000", out_point="00:00:03.000",
                        caption="Intro Shot")
        filt_mod.add_filter(session, "brightness", track_index=1, clip_index=0,
                            params={"level": "1.4"})

        with tempfile.NamedTemporaryFile(suffix=".mlt", delete=False) as f:
            path = f.name
        try:
            proj_mod.save_project(session, path)
            assert not session.is_modified

            # Reopen in fresh session
            s2 = Session()
            result = proj_mod.open_project(s2, path)
            assert result["track_count"] >= 3
            assert result["media_clip_count"] >= 1

            info = proj_mod.project_info(s2)
            assert any("1.mp4" in c["resource"] for c in info["media_clips"])

            # Verify filter survived
            producers = get_all_producers(s2.root)
            found = False
            for p in producers:
                for f in p.findall("filter"):
                    if get_property(f, "mlt_service") == "brightness":
                        assert get_property(f, "level") == "1.4"
                        found = True
            assert found
        finally:
            os.unlink(path)

    def test_save_overwrite(self, session):
        """Save twice to the same path — should overwrite."""
        with tempfile.NamedTemporaryFile(suffix=".mlt", delete=False) as f:
            path = f.name
        try:
            proj_mod.save_project(session, path)
            tl_mod.add_track(session, "video")
            proj_mod.save_project(session, path)

            s2 = Session()
            proj_mod.open_project(s2, path)
            tracks = tl_mod.list_tracks(s2)
            assert len(tracks) >= 2
        finally:
            os.unlink(path)

    def test_project_info_comprehensive(self, session_with_tracks, video):
        """project info should report everything."""
        s = session_with_tracks
        tl_mod.add_clip(s, video, 1, "00:00:00.000", "00:00:02.000")
        tl_mod.add_clip(s, video, 1, "00:00:02.000", "00:00:04.000")
        tl_mod.add_clip(s, video, 2, "00:00:00.000", "00:00:03.000")

        info = proj_mod.project_info(s)
        assert info["modified"] is True
        assert len(info["tracks"]) >= 4  # bg + V1 + V2 + A1
        assert len(info["media_clips"]) >= 3
        # Check track types
        types = [t["type"] for t in info["tracks"]]
        assert "video" in types
        assert "audio" in types

    def test_project_xml_output(self, session, video):
        """project xml should produce valid MLT XML."""
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:01.000")
        xml_str = mlt_to_string(session.root)
        assert '<?xml' in xml_str
        assert '<mlt' in xml_str
        assert 'Shotcut' in xml_str
        assert '1.mp4' in xml_str


# ============================================================================
# 2. TIMELINE — all track and clip operations
# ============================================================================

class TestTimelineTracks:
    """Test every track operation."""

    def test_add_multiple_tracks(self, session):
        """Add many tracks of both types."""
        for i in range(5):
            tl_mod.add_track(session, "video", f"V{i+1}")
        for i in range(3):
            tl_mod.add_track(session, "audio", f"A{i+1}")
        tracks = tl_mod.list_tracks(session)
        video_tracks = [t for t in tracks if t["type"] == "video"]
        audio_tracks = [t for t in tracks if t["type"] == "audio"]
        assert len(video_tracks) == 5
        assert len(audio_tracks) == 3

    def test_remove_middle_track(self, session_with_tracks):
        """Remove a track in the middle."""
        s = session_with_tracks
        before = len(tl_mod.list_tracks(s))
        # V1 is index 1, V2 is index 2, A1 is index 3
        tl_mod.remove_track(s, 2)  # remove V2
        after = tl_mod.list_tracks(s)
        assert len(after) == before - 1

    def test_remove_track_out_of_range(self, session):
        with pytest.raises(IndexError):
            tl_mod.remove_track(session, 99)

    def test_track_naming(self, session):
        tl_mod.add_track(session, "video")
        tl_mod.set_track_name(session, 1, "My Custom Track")
        tracks = tl_mod.list_tracks(session)
        assert tracks[1]["name"] == "My Custom Track"

        # Rename again
        tl_mod.set_track_name(session, 1, "Renamed")
        tracks = tl_mod.list_tracks(session)
        assert tracks[1]["name"] == "Renamed"

    def test_mute_audio_track(self, session):
        tl_mod.add_track(session, "audio", "A1")
        idx = len(tl_mod.list_tracks(session)) - 1

        result = tl_mod.set_track_mute(session, idx, True)
        assert "audio" in result["hide"] or result["hide"] == "both"

        result = tl_mod.set_track_mute(session, idx, False)
        assert result["hide"] in ("", "video")

    def test_hide_video_track(self, session):
        tl_mod.add_track(session, "video", "V1")
        result = tl_mod.set_track_hidden(session, 1, True)
        assert "video" in result["hide"] or result["hide"] == "both"

        result = tl_mod.set_track_hidden(session, 1, False)
        assert result["hide"] in ("", "audio")

    def test_mute_then_hide_same_track(self, session):
        """Muting then hiding should result in hide='both'."""
        tl_mod.add_track(session, "video", "V1")
        tl_mod.set_track_mute(session, 1, True)
        result = tl_mod.set_track_hidden(session, 1, True)
        assert result["hide"] == "both"

        # Unmute but keep hidden
        result = tl_mod.set_track_mute(session, 1, False)
        assert result["hide"] == "video"


class TestTimelineClips:
    """Test every clip operation with real video."""

    def test_add_single_clip(self, session, video):
        tl_mod.add_track(session, "video")
        result = tl_mod.add_clip(session, video, 1,
                                 in_point="00:00:00.000", out_point="00:00:05.000")
        assert result["resource"] == os.path.abspath(video)
        clips = tl_mod.list_clips(session, 1)
        real_clips = [c for c in clips if "clip_index" in c]
        assert len(real_clips) == 1

    def test_add_multiple_clips_sequential(self, session, video):
        """Add 5 clips sequentially to simulate a rough cut."""
        tl_mod.add_track(session, "video", "V1")
        for i in range(5):
            start = f"00:00:{i*2:02d}.000"
            end = f"00:00:{i*2+2:02d}.000"
            tl_mod.add_clip(session, video, 1,
                            in_point=start, out_point=end,
                            caption=f"Scene {i+1}")

        clips = tl_mod.list_clips(session, 1)
        real_clips = [c for c in clips if "clip_index" in c]
        assert len(real_clips) == 5
        assert real_clips[0]["caption"] == "Scene 1"
        assert real_clips[4]["caption"] == "Scene 5"

    def test_add_clip_at_position(self, session, video):
        """Insert a clip at a specific position (not append)."""
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:02.000", caption="First")
        tl_mod.add_clip(session, video, 1, "00:00:04.000", "00:00:06.000", caption="Third")
        # Insert between them
        tl_mod.add_clip(session, video, 1, "00:00:02.000", "00:00:04.000",
                        position=1, caption="Second")

        clips = tl_mod.list_clips(session, 1)
        real_clips = [c for c in clips if "clip_index" in c]
        assert len(real_clips) == 3
        assert real_clips[0]["caption"] == "First"
        assert real_clips[1]["caption"] == "Second"
        assert real_clips[2]["caption"] == "Third"

    def test_remove_clip_ripple(self, session, video):
        """Remove with ripple — no gap left."""
        tl_mod.add_track(session, "video")
        for i in range(3):
            tl_mod.add_clip(session, video, 1, f"00:00:{i*2:02d}.000",
                            f"00:00:{i*2+2:02d}.000")

        tl_mod.remove_clip(session, 1, 1, ripple=True)
        clips = [c for c in tl_mod.list_clips(session, 1) if "clip_index" in c]
        assert len(clips) == 2

    def test_remove_clip_no_ripple(self, session, video):
        """Remove without ripple — leaves a blank."""
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:03.000")
        tl_mod.add_clip(session, video, 1, "00:00:03.000", "00:00:06.000")

        tl_mod.remove_clip(session, 1, 0, ripple=False)
        items = tl_mod.list_clips(session, 1)
        types = [item.get("type") for item in items if "type" in item]
        assert "blank" in types

    def test_trim_clip_in(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:10.000")
        result = tl_mod.trim_clip(session, 1, 0, in_point="00:00:03.000")
        assert result["new_in"] == "00:00:03.000"
        assert result["new_out"] == "00:00:10.000"

    def test_trim_clip_out(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:10.000")
        result = tl_mod.trim_clip(session, 1, 0, out_point="00:00:07.000")
        assert result["new_in"] == "00:00:00.000"
        assert result["new_out"] == "00:00:07.000"

    def test_trim_both_ends(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:10.000")
        result = tl_mod.trim_clip(session, 1, 0,
                                  in_point="00:00:02.000", out_point="00:00:08.000")
        assert result["new_in"] == "00:00:02.000"
        assert result["new_out"] == "00:00:08.000"

    def test_split_clip(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:10.000")
        result = tl_mod.split_clip(session, 1, 0, "00:00:05.000")

        assert result["first_clip"]["in"] == "00:00:00.000"
        assert result["first_clip"]["out"] == "00:00:05.000"
        assert result["second_clip"]["in"] == "00:00:05.000"
        assert result["second_clip"]["out"] == "00:00:10.000"

        clips = [c for c in tl_mod.list_clips(session, 1) if "clip_index" in c]
        assert len(clips) == 2

    def test_split_then_remove_first_half(self, session, video):
        """Split and delete the first part — common 'remove intro' workflow."""
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:10.000")
        tl_mod.split_clip(session, 1, 0, "00:00:03.000")
        tl_mod.remove_clip(session, 1, 0, ripple=True)

        clips = [c for c in tl_mod.list_clips(session, 1) if "clip_index" in c]
        assert len(clips) == 1
        assert clips[0]["in"] == "00:00:03.000"

    def test_move_clip_between_tracks(self, session, video):
        tl_mod.add_track(session, "video", "V1")
        tl_mod.add_track(session, "video", "V2")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000")

        tl_mod.move_clip(session, 1, 0, 2)

        clips_v1 = [c for c in tl_mod.list_clips(session, 1) if "clip_index" in c]
        clips_v2 = [c for c in tl_mod.list_clips(session, 2) if "clip_index" in c]
        assert len(clips_v1) == 0
        assert len(clips_v2) == 1

    def test_move_clip_reorder_on_same_track(self, session, video):
        """Move a clip to a specific position on the same track."""
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:02.000", caption="A")
        tl_mod.add_clip(session, video, 1, "00:00:02.000", "00:00:04.000", caption="B")
        tl_mod.add_clip(session, video, 1, "00:00:04.000", "00:00:06.000", caption="C")

        # Move "A" (index 0) to the end (effectively swap A to after C)
        tl_mod.move_clip(session, 1, 0, 1)  # same track, appends
        clips = [c for c in tl_mod.list_clips(session, 1) if "clip_index" in c]
        # B and C should now be before A
        assert clips[0]["caption"] == "B"

    def test_add_blank_gap(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:03.000")
        tl_mod.add_blank(session, 1, "00:00:02.000")
        tl_mod.add_clip(session, video, 1, "00:00:03.000", "00:00:06.000")

        items = tl_mod.list_clips(session, 1)
        assert any(i.get("type") == "blank" for i in items)

    def test_show_timeline_with_content(self, session, video):
        tl_mod.add_track(session, "video", "V1")
        tl_mod.add_track(session, "audio", "A1")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000", caption="Shot1")
        tl_mod.add_clip(session, video, 1, "00:00:05.000", "00:00:10.000", caption="Shot2")

        result = tl_mod.show_timeline(session)
        assert result["fps_num"] == 30000
        assert len(result["tracks"]) >= 3

        v1 = [t for t in result["tracks"] if t.get("name") == "V1"][0]
        assert len([c for c in v1["clips"] if "clip_index" in c]) == 2

    def test_clip_index_out_of_range(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:01.000")
        with pytest.raises(IndexError):
            tl_mod.remove_clip(session, 1, 99)

    def test_track_index_out_of_range(self, session):
        with pytest.raises(IndexError):
            tl_mod.list_clips(session, 99)


# ============================================================================
# 3. FILTERS — all filter operations
# ============================================================================

class TestFilters:
    """Test every filter operation."""

    def test_list_all_filters(self):
        result = filt_mod.list_available_filters()
        assert len(result) > 10
        names = {f["name"] for f in result}
        assert "brightness" in names
        assert "volume" in names
        assert "blur" in names
        assert "text" in names
        assert "sepia" in names
        assert "affine" in names
        assert "speed" in names

    def test_filter_info_all_registered(self):
        """Every registered filter should return valid info."""
        for f in filt_mod.list_available_filters():
            info = filt_mod.get_filter_info(f["name"])
            assert "service" in info
            assert "params" in info

    def test_add_every_filter_type(self, session, video):
        """Apply every registered filter to a clip."""
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000")

        all_filters = filt_mod.list_available_filters()
        for finfo in all_filters:
            result = filt_mod.add_filter(session, finfo["name"],
                                         track_index=1, clip_index=0)
            assert result["service"] == finfo["service"]

        # All filters should be attached
        attached = filt_mod.list_filters(session, track_index=1, clip_index=0)
        assert len(attached) == len(all_filters)

    def test_filter_with_custom_params(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000")

        result = filt_mod.add_filter(session, "text", track_index=1, clip_index=0,
                                     params={
                                         "argument": "Hello World",
                                         "size": "72",
                                         "fgcolour": "#ff0000ff",
                                         "halign": "center",
                                         "valign": "bottom",
                                     })
        assert result["params"]["argument"] == "Hello World"
        assert result["params"]["size"] == "72"

    def test_remove_filter_by_index(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000")

        filt_mod.add_filter(session, "brightness", track_index=1, clip_index=0)
        filt_mod.add_filter(session, "sepia", track_index=1, clip_index=0)
        filt_mod.add_filter(session, "blur", track_index=1, clip_index=0)

        # Remove the middle one (sepia, index 1)
        result = filt_mod.remove_filter(session, 1, track_index=1, clip_index=0)
        assert result["service"] == "sepia"

        remaining = filt_mod.list_filters(session, track_index=1, clip_index=0)
        services = [f["service"] for f in remaining]
        assert "sepia" not in services
        assert "brightness" in services
        assert len(remaining) == 2

    def test_set_filter_param(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000")
        filt_mod.add_filter(session, "brightness", track_index=1, clip_index=0)

        result = filt_mod.set_filter_param(session, 0, "level", "0.3",
                                            track_index=1, clip_index=0)
        assert result["old_value"] == "1.0"
        assert result["new_value"] == "0.3"

        # Verify
        filters = filt_mod.list_filters(session, track_index=1, clip_index=0)
        assert filters[0]["params"]["level"] == "0.3"

    def test_filter_on_track_level(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000")

        result = filt_mod.add_filter(session, "brightness", track_index=1)
        assert result["target"] == "track 1"

        filters = filt_mod.list_filters(session, track_index=1)
        assert len(filters) >= 1

    def test_global_filter(self, session):
        result = filt_mod.add_filter(session, "brightness")
        assert result["target"] == "global"

        filters = filt_mod.list_filters(session)
        assert len(filters) >= 1

    def test_filter_index_out_of_range(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:01.000")
        with pytest.raises(IndexError):
            filt_mod.remove_filter(session, 99, track_index=1, clip_index=0)

    def test_raw_mlt_service_name(self, session, video):
        """Use a raw MLT service name not in the registry."""
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000")
        result = filt_mod.add_filter(session, "greyscale", track_index=1, clip_index=0)
        assert result["service"] == "greyscale"


# ============================================================================
# 4. MEDIA — probe, list, check
# ============================================================================

class TestMedia:
    def test_probe_real_video(self, video):
        result = media_mod.probe_media(video)
        assert result["filename"] == "1.mp4"
        assert result["size_bytes"] > 0

    def test_list_media_after_adding_clips(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000")
        tl_mod.add_clip(session, video, 1, "00:00:05.000", "00:00:10.000")

        media = media_mod.list_media(session)
        assert len(media) >= 2
        for m in media:
            assert m["exists"] is True

    def test_check_media_all_present(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000")

        result = media_mod.check_media_files(session)
        assert result["all_present"] is True
        assert len(result["missing"]) == 0

    def test_check_media_with_missing(self, session, video):
        """Simulate a missing media reference."""
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000")

        # Manually add a producer with a bad path
        create_producer(session.root, "/nonexistent/missing_video.mp4",
                        "00:00:00.000", "00:00:10.000")

        result = media_mod.check_media_files(session)
        assert not result["all_present"]
        assert any("missing_video" in p for p in result["missing"])

    def test_probe_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            media_mod.probe_media("/no/such/file.mp4")


# ============================================================================
# 5. EXPORT — presets and render
# ============================================================================

class TestExport:
    def test_all_presets_valid(self):
        presets = export_mod.list_presets()
        assert len(presets) >= 10
        for p in presets:
            info = export_mod.get_preset_info(p["name"])
            assert "description" in info

    def test_render_generates_script_without_tools(self, session, video):
        """Without melt/ffmpeg, render should generate a script."""
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            out = f.name
        os.unlink(out)  # Remove so it doesn't exist

        try:
            result = export_mod.render(session, out, "default")
            # Without melt/ffmpeg, should get a script or error
            assert result.get("action") in ("render", "render_script")
        except RuntimeError:
            # "No renderable clips" or "no tools" are acceptable
            pass

    def test_render_refuses_overwrite(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"existing content")
            out = f.name
        try:
            with pytest.raises(FileExistsError):
                export_mod.render(session, out, "default")
        finally:
            os.unlink(out)

    def test_render_with_overwrite(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"old")
            out = f.name
        try:
            result = export_mod.render(session, out, "default", overwrite=True)
            assert result.get("action") in ("render", "render_script")
        except RuntimeError:
            pass  # No rendering tools available
        finally:
            if os.path.exists(out):
                os.unlink(out)

    def test_render_invalid_preset(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000")
        with pytest.raises(ValueError):
            export_mod.render(session, "/tmp/out.mp4", "fake_preset")


# ============================================================================
# 6. SESSION — undo/redo/state
# ============================================================================

class TestSession:
    def test_undo_redo_chain(self, session, video):
        """Multiple undo/redo steps."""
        tl_mod.add_track(session, "video", "V1")       # step 1
        tl_mod.add_track(session, "audio", "A1")       # step 2
        tl_mod.add_clip(session, video, 1,
                        "00:00:00.000", "00:00:05.000") # step 3

        assert len(tl_mod.list_tracks(session)) == 3  # bg + V1 + A1
        clips = [c for c in tl_mod.list_clips(session, 1) if "clip_index" in c]
        assert len(clips) == 1

        # Undo add-clip
        session.undo()
        clips = [c for c in tl_mod.list_clips(session, 1) if "clip_index" in c]
        assert len(clips) == 0

        # Undo add audio track
        session.undo()
        assert len(tl_mod.list_tracks(session)) == 2  # bg + V1

        # Redo audio track
        session.redo()
        assert len(tl_mod.list_tracks(session)) == 3

        # Redo add-clip
        session.redo()
        clips = [c for c in tl_mod.list_clips(session, 1) if "clip_index" in c]
        assert len(clips) == 1

    def test_undo_clears_redo_on_new_action(self, session, video):
        """New action after undo should clear redo stack."""
        tl_mod.add_track(session, "video")
        tl_mod.add_track(session, "audio")

        session.undo()
        assert session.redo()  # redo is available

        # But doing a new action should clear redo
        session.undo()
        tl_mod.add_track(session, "video", "V2")  # new action
        assert not session.redo()  # redo should be gone

    def test_undo_filter_operations(self, session, video):
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000")

        filt_mod.add_filter(session, "brightness", track_index=1, clip_index=0,
                            params={"level": "1.5"})
        assert len(filt_mod.list_filters(session, 1, 0)) == 1

        filt_mod.set_filter_param(session, 0, "level", "0.5",
                                   track_index=1, clip_index=0)

        # Undo the param change
        session.undo()
        filters = filt_mod.list_filters(session, 1, 0)
        assert filters[0]["params"]["level"] == "1.5"

        # Undo the filter add
        session.undo()
        assert len(filt_mod.list_filters(session, 1, 0)) == 0

    def test_session_status(self, session, video):
        status = session.status()
        assert status["project_open"] is True
        assert status["undo_available"] == 0

        tl_mod.add_track(session, "video")
        status = session.status()
        assert status["undo_available"] == 1
        assert status["modified"] is True

    def test_session_persist_and_list(self, session):
        path = session.save_session_state()
        assert os.path.isfile(path)

        sessions = Session.list_sessions()
        ids = [s["session_id"] for s in sessions]
        assert session.session_id in ids

        # Cleanup
        os.unlink(path)

    def test_many_undos(self, session, video):
        """Undo more times than there are operations — should not crash."""
        tl_mod.add_track(session, "video")
        for _ in range(3):
            assert session.undo() or True  # Don't care if it fails
        # Extra undos should return False, not crash
        assert not session.undo()


# ============================================================================
# 7. TIMECODE UTILITIES — edge cases
# ============================================================================

class TestTimecodeEdgeCases:
    def test_zero(self):
        assert timecode_to_frames("0") == 0
        assert frames_to_timecode(0) == "00:00:00.000"

    def test_large_timecode(self):
        frames = timecode_to_frames("02:30:00.000")
        tc = frames_to_timecode(frames)
        # At 29.97fps, 02:30:00.000 doesn't land on an exact frame boundary,
        # so the roundtrip may be off by ~1 frame (~33ms). Verify it's close.
        roundtrip_frames = timecode_to_frames(tc)
        assert abs(roundtrip_frames - frames) <= 1

    def test_fractional_seconds(self):
        frames = timecode_to_frames("0.5")
        assert frames > 0

    def test_format_duration(self):
        assert "frames" in format_duration(5)
        assert ":" in format_duration(300)

    def test_all_timecode_formats(self):
        """Test all accepted timecode formats parse correctly."""
        assert timecode_to_frames("100") == 100
        assert timecode_to_frames("1.5") > 0
        assert timecode_to_frames("00:00:01.000") > 0
        assert timecode_to_frames("00:00:01:15") > 0
        assert timecode_to_frames("00:01:00") > 0


# ============================================================================
# 8. COMPLEX REAL-WORLD WORKFLOWS
# ============================================================================

class TestRealWorldWorkflows:
    """Composite tests that simulate complete, realistic editing sessions."""

    def test_youtube_video_edit(self, session, video):
        """Simulate editing a YouTube video:
        - Multiple clips on timeline
        - Trim intro/outro
        - Add text overlay
        - Apply color correction
        - Add background music track
        - Export
        """
        # Setup tracks
        tl_mod.add_track(session, "video", "Main")
        tl_mod.add_track(session, "video", "B-Roll")
        tl_mod.add_track(session, "audio", "Music")
        tl_mod.add_track(session, "audio", "Voiceover")

        # Add clips to main track
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:03.000",
                        caption="Intro")
        tl_mod.add_clip(session, video, 1, "00:00:03.000", "00:00:08.000",
                        caption="Main Content")
        tl_mod.add_clip(session, video, 1, "00:00:08.000", "00:00:10.000",
                        caption="Outro")

        # Add b-roll on V2
        tl_mod.add_clip(session, video, 2, "00:00:01.000", "00:00:04.000",
                        caption="B-Roll Overlay")

        # Trim the intro — remove first second
        tl_mod.trim_clip(session, 1, 0, in_point="00:00:01.000")

        # Add title text to intro
        filt_mod.add_filter(session, "text", track_index=1, clip_index=0,
                            params={
                                "argument": "MY AWESOME VIDEO",
                                "size": "64",
                                "fgcolour": "#ffffffff",
                                "halign": "center",
                                "valign": "middle",
                            })

        # Color correct main content
        filt_mod.add_filter(session, "brightness", track_index=1, clip_index=1,
                            params={"level": "1.1"})
        filt_mod.add_filter(session, "saturation", track_index=1, clip_index=1,
                            params={"saturation": "1.2"})

        # Fade in on intro
        filt_mod.add_filter(session, "fadein-video", track_index=1, clip_index=0)

        # Fade out on outro
        filt_mod.add_filter(session, "fadeout-video", track_index=1, clip_index=2)

        # Mute b-roll audio (we have separate voiceover)
        tl_mod.set_track_mute(session, 2, True)

        # Verify the timeline
        timeline = tl_mod.show_timeline(session)
        main_track = [t for t in timeline["tracks"] if t.get("name") == "Main"][0]
        assert len([c for c in main_track["clips"] if "clip_index" in c]) == 3

        # Save
        with tempfile.NamedTemporaryFile(suffix=".mlt", delete=False) as f:
            path = f.name
        proj_mod.save_project(session, path)

        # Verify save roundtrip
        s2 = Session()
        proj_mod.open_project(s2, path)
        info = proj_mod.project_info(s2)
        assert len(info["tracks"]) >= 5  # bg + 4 tracks
        os.unlink(path)

    def test_montage_sequence(self, session, video):
        """Create a montage: many short clips with transitions.
        Split one long clip into many segments, apply different effects.
        """
        tl_mod.add_track(session, "video", "Montage")

        # Add a long clip and split it into 5 segments
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:10.000")

        tl_mod.split_clip(session, 1, 0, "00:00:02.000")
        tl_mod.split_clip(session, 1, 1, "00:00:04.000")
        tl_mod.split_clip(session, 1, 2, "00:00:06.000")
        tl_mod.split_clip(session, 1, 3, "00:00:08.000")

        clips = [c for c in tl_mod.list_clips(session, 1) if "clip_index" in c]
        assert len(clips) == 5

        # Apply a different effect to each segment
        effects = ["sepia", "charcoal", "brightness", "glow", "saturation"]
        for i, effect in enumerate(effects):
            filt_mod.add_filter(session, effect, track_index=1, clip_index=i)

        # Verify all filters
        for i in range(5):
            filters = filt_mod.list_filters(session, track_index=1, clip_index=i)
            assert len(filters) >= 1

    def test_multicam_edit(self, session, video):
        """Simulate multicam editing:
        - 3 camera angles on separate tracks
        - Use hide/show to switch between cameras
        - Apply consistent color grade to all
        """
        tl_mod.add_track(session, "video", "Cam1-Wide")
        tl_mod.add_track(session, "video", "Cam2-Medium")
        tl_mod.add_track(session, "video", "Cam3-Close")
        tl_mod.add_track(session, "audio", "Master Audio")

        # Each camera has full-length footage
        for track_idx in [1, 2, 3]:
            tl_mod.add_clip(session, video, track_idx,
                            "00:00:00.000", "00:00:10.000",
                            caption=f"Camera {track_idx}")

        # Apply same color grade to all cameras
        for track_idx in [1, 2, 3]:
            filt_mod.add_filter(session, "brightness", track_index=track_idx,
                                clip_index=0, params={"level": "1.05"})
            filt_mod.add_filter(session, "saturation", track_index=track_idx,
                                clip_index=0, params={"saturation": "0.9"})

        # "Switch" cameras by hiding/showing tracks
        # Show Cam1 first, hide others
        tl_mod.set_track_hidden(session, 2, True)
        tl_mod.set_track_hidden(session, 3, True)

        # Verify track states
        tracks = tl_mod.list_tracks(session)
        cam1 = tracks[1]
        cam2 = tracks[2]
        cam3 = tracks[3]
        assert "video" not in cam1.get("hide", "")
        assert "video" in cam2.get("hide", "")
        assert "video" in cam3.get("hide", "")

    def test_audio_podcast_edit(self, session, video):
        """Edit an audio podcast:
        - Multiple audio segments
        - Volume adjustments
        - Fade in/out
        - Remove a bad section (split + delete)
        """
        tl_mod.add_track(session, "audio", "Host")
        tl_mod.add_track(session, "audio", "Guest")

        # Use the video file as audio source (it has audio too)
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:10.000",
                        caption="Host Recording")
        tl_mod.add_clip(session, video, 2, "00:00:00.000", "00:00:10.000",
                        caption="Guest Recording")

        # Adjust guest volume down a bit
        filt_mod.add_filter(session, "volume", track_index=2, clip_index=0,
                            params={"gain": "-3.0"})

        # Fade in the host at the start
        filt_mod.add_filter(session, "fadein-audio", track_index=1, clip_index=0)

        # Split host recording to remove a "um" at 5 seconds
        tl_mod.split_clip(session, 1, 0, "00:00:05.000")
        tl_mod.split_clip(session, 1, 1, "00:00:06.000")
        # Remove the middle segment (the "um")
        tl_mod.remove_clip(session, 1, 1, ripple=True)

        clips = [c for c in tl_mod.list_clips(session, 1) if "clip_index" in c]
        assert len(clips) == 2

    def test_picture_in_picture(self, session, video):
        """Simulate picture-in-picture:
        - Main video on V1
        - PIP overlay on V2 with position/scale filter
        """
        tl_mod.add_track(session, "video", "Main")
        tl_mod.add_track(session, "video", "PIP")

        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:10.000",
                        caption="Main Video")
        tl_mod.add_clip(session, video, 2, "00:00:02.000", "00:00:08.000",
                        caption="PIP Overlay")

        # Scale and position the PIP to bottom-right corner
        filt_mod.add_filter(session, "affine", track_index=2, clip_index=0,
                            params={
                                "transition.geometry": "70%/70%:25%x25%:100",
                            })

        # Verify
        filters = filt_mod.list_filters(session, track_index=2, clip_index=0)
        assert any(f["service"] == "affine" for f in filters)

    def test_color_grading_pipeline(self, session, video):
        """Apply a multi-step color grading pipeline to a clip."""
        tl_mod.add_track(session, "video")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:10.000")

        # Step 1: Brightness
        filt_mod.add_filter(session, "brightness", track_index=1, clip_index=0,
                            params={"level": "0.95"})
        # Step 2: Saturation boost
        filt_mod.add_filter(session, "saturation", track_index=1, clip_index=0,
                            params={"saturation": "1.3"})
        # Step 3: Hue shift for "teal and orange" look
        filt_mod.add_filter(session, "hue", track_index=1, clip_index=0,
                            params={"shift": "0.05"})
        # Step 4: Glow for soft look
        filt_mod.add_filter(session, "glow", track_index=1, clip_index=0,
                            params={"blur": "0.3"})

        filters = filt_mod.list_filters(session, track_index=1, clip_index=0)
        assert len(filters) == 4

        # Adjust step 2 after preview
        filt_mod.set_filter_param(session, 1, "saturation", "1.1",
                                   track_index=1, clip_index=0)

        # Undo the adjustment
        session.undo()
        filters = filt_mod.list_filters(session, 1, 0)
        assert filters[1]["params"]["saturation"] == "1.3"

    def test_undo_heavy_session(self, session, video):
        """Lots of operations, then undo them all back to start."""
        initial_xml = mlt_to_string(session.root)

        tl_mod.add_track(session, "video", "V1")
        tl_mod.add_track(session, "audio", "A1")
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:05.000")
        filt_mod.add_filter(session, "brightness", track_index=1, clip_index=0)
        tl_mod.trim_clip(session, 1, 0, in_point="00:00:01.000")
        filt_mod.set_filter_param(session, 0, "level", "0.5",
                                   track_index=1, clip_index=0)
        tl_mod.add_clip(session, video, 1, "00:00:05.000", "00:00:10.000")
        tl_mod.set_track_name(session, 1, "Renamed")
        tl_mod.set_track_mute(session, 2, True)

        # Count undos available
        status = session.status()
        assert status["undo_available"] == 9  # Each operation = 1 checkpoint

        # Undo all 9
        for _ in range(9):
            assert session.undo()

        # Should be back to initial state (no tracks beyond background)
        final_tracks = tl_mod.list_tracks(session)
        assert len(final_tracks) == 1  # Only background

    def test_save_load_complex_project(self, session, video):
        """Build a complex project, save, reload, verify every detail."""
        # Build
        tl_mod.add_track(session, "video", "V1")
        tl_mod.add_track(session, "video", "V2")
        tl_mod.add_track(session, "audio", "A1")

        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:03.000", caption="Shot-A")
        tl_mod.add_clip(session, video, 1, "00:00:03.000", "00:00:06.000", caption="Shot-B")
        tl_mod.add_clip(session, video, 2, "00:00:00.000", "00:00:04.000", caption="Overlay")
        tl_mod.add_blank(session, 3, "00:00:02.000")

        filt_mod.add_filter(session, "brightness", track_index=1, clip_index=0,
                            params={"level": "1.2"})
        filt_mod.add_filter(session, "text", track_index=2, clip_index=0,
                            params={"argument": "TITLE", "size": "96"})
        filt_mod.add_filter(session, "volume", track_index=3)

        tl_mod.set_track_mute(session, 2, True)
        tl_mod.set_track_name(session, 3, "Background Music")

        # Save
        with tempfile.NamedTemporaryFile(suffix=".mlt", delete=False) as f:
            path = f.name
        proj_mod.save_project(session, path)

        # Reload in fresh session
        s2 = Session()
        proj_mod.open_project(s2, path)

        # Verify tracks
        tracks = tl_mod.list_tracks(s2)
        assert len(tracks) == 4  # bg + V1 + V2 + A1
        assert tracks[3]["name"] == "Background Music"

        # Verify clips
        v1_clips = [c for c in tl_mod.list_clips(s2, 1) if "clip_index" in c]
        assert len(v1_clips) == 2
        assert v1_clips[0]["caption"] == "Shot-A"
        assert v1_clips[1]["caption"] == "Shot-B"

        v2_clips = [c for c in tl_mod.list_clips(s2, 2) if "clip_index" in c]
        assert len(v2_clips) == 1

        # Verify audio track has blank + nothing else
        a1_items = tl_mod.list_clips(s2, 3)
        blanks = [i for i in a1_items if i.get("type") == "blank"]
        assert len(blanks) >= 1

        # Verify filters survived
        producers = get_all_producers(s2.root)
        brightness_found = False
        text_found = False
        for p in producers:
            for f in p.findall("filter"):
                svc = get_property(f, "mlt_service")
                if svc == "brightness":
                    assert get_property(f, "level") == "1.2"
                    brightness_found = True
                if svc == "dynamictext":
                    assert get_property(f, "argument") == "TITLE"
                    text_found = True
        assert brightness_found
        assert text_found

        os.unlink(path)

    def test_iterative_refinement(self, session, video):
        """Simulate iterative editing: add, preview, adjust, repeat.
        Tests that the state stays consistent through many mutations.
        """
        tl_mod.add_track(session, "video", "Main")

        # Round 1: rough cut
        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:10.000")

        # Round 2: split into segments
        tl_mod.split_clip(session, 1, 0, "00:00:05.000")
        clips = [c for c in tl_mod.list_clips(session, 1) if "clip_index" in c]
        assert len(clips) == 2

        # Round 3: add filter, then change mind
        filt_mod.add_filter(session, "sepia", track_index=1, clip_index=0)
        session.undo()  # Actually, no sepia
        filt_mod.add_filter(session, "saturation", track_index=1, clip_index=0,
                            params={"saturation": "1.5"})

        # Round 4: trim second clip
        tl_mod.trim_clip(session, 1, 1, in_point="00:00:06.000", out_point="00:00:09.000")

        # Round 5: add a new clip in between
        tl_mod.add_clip(session, video, 1, "00:00:05.000", "00:00:06.000",
                        position=1, caption="Insert")

        clips = [c for c in tl_mod.list_clips(session, 1) if "clip_index" in c]
        assert len(clips) == 3
        assert clips[1]["caption"] == "Insert"

        # Verify filter is still on first clip
        filters = filt_mod.list_filters(session, 1, 0)
        assert any(f["service"] == "frei0r.saturat0r" for f in filters)

    def test_full_timeline_visualization(self, session, video):
        """Build a complex timeline and verify show_timeline returns coherent data."""
        tl_mod.add_track(session, "video", "V1")
        tl_mod.add_track(session, "video", "V2")
        tl_mod.add_track(session, "audio", "A1")

        tl_mod.add_clip(session, video, 1, "00:00:00.000", "00:00:03.000", caption="Intro")
        tl_mod.add_blank(session, 1, "00:00:01.000")
        tl_mod.add_clip(session, video, 1, "00:00:03.000", "00:00:08.000", caption="Body")
        tl_mod.add_clip(session, video, 2, "00:00:01.000", "00:00:05.000", caption="Cutaway")

        result = tl_mod.show_timeline(session)

        # Check structure
        assert "fps_num" in result
        tracks = result["tracks"]
        v1 = [t for t in tracks if t.get("name") == "V1"][0]
        v2 = [t for t in tracks if t.get("name") == "V2"][0]
        a1 = [t for t in tracks if t.get("name") == "A1"][0]

        # V1 should have: clip, blank, clip
        v1_items = v1["clips"]
        assert len(v1_items) == 3
        assert v1_items[1].get("type") == "blank"

        # V2 has 1 clip
        v2_clips = [c for c in v2["clips"] if "clip_index" in c]
        assert len(v2_clips) == 1

        # A1 is empty
        assert len(a1.get("clips", [])) == 0


# ============================================================================
# 9. CLI COMMAND-LINE INTERFACE (subprocess tests)
# ============================================================================

def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = name.replace("cli-anything-", "cli_anything.") + "." + name.split("-")[-1] + "_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


class TestCLISubprocess:
    """Test the actual CLI entry point via subprocess."""
    CLI_BASE = _resolve_cli("cli-anything-shotcut")

    def _run(self, *args, json_mode=False):
        import subprocess
        cmd = list(self.CLI_BASE)
        if json_mode:
            cmd.append("--json")
        cmd.extend(args)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result

    def test_help(self):
        r = self._run("--help")
        assert r.returncode == 0
        assert "Shotcut CLI" in r.stdout

    def test_project_new(self):
        with tempfile.NamedTemporaryFile(suffix=".mlt", delete=False) as f:
            path = f.name
        try:
            r = self._run("project", "new", "--profile", "hd1080p30", "-o", path)
            assert r.returncode == 0
            assert "Created" in r.stdout
            assert os.path.isfile(path)
        finally:
            os.unlink(path)

    def test_project_info_json(self):
        with tempfile.NamedTemporaryFile(suffix=".mlt", delete=False) as f:
            path = f.name
        try:
            self._run("project", "new", "--profile", "hd1080p30", "-o", path)
            r = self._run("--json", "--project", path, "project", "info")
            assert r.returncode == 0
            data = json.loads(r.stdout)
            assert data["profile"]["width"] == "1920"
        finally:
            os.unlink(path)

    def test_profiles_list(self):
        r = self._run("project", "profiles")
        assert r.returncode == 0
        assert "hd1080p30" in r.stdout

    def test_filter_list_available(self):
        r = self._run("filter", "list-available")
        assert r.returncode == 0
        assert "brightness" in r.stdout

    def test_filter_info(self):
        r = self._run("filter", "info", "text")
        assert r.returncode == 0
        assert "dynamictext" in r.stdout
        assert "argument" in r.stdout

    def test_export_presets(self):
        r = self._run("export", "presets")
        assert r.returncode == 0
        assert "h264" in r.stdout

    def test_media_probe(self):
        r = self._run("media", "probe", VIDEO)
        assert r.returncode == 0
        assert "1.mp4" in r.stdout

    def test_media_probe_json(self):
        r = self._run("media", "probe", VIDEO, json_mode=True)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["filename"] == "1.mp4"

    def test_full_pipeline_subprocess(self):
        """Full editing pipeline as CLI subprocess calls."""
        with tempfile.NamedTemporaryFile(suffix=".mlt", delete=False) as f:
            path = f.name

        try:
            # Create project
            r = self._run("project", "new", "--profile", "hd1080p30", "-o", path)
            assert r.returncode == 0

            # Note: each subprocess invocation is stateless (loads from file).
            # The --project flag reopens, but doesn't persist track additions
            # across invocations (since session is in-memory).
            # This tests the CLI interface itself, not cross-invocation state.

            # JSON info
            r = self._run("--json", "--project", path, "project", "info")
            assert r.returncode == 0
            data = json.loads(r.stdout)
            assert data["profile"]["height"] == "1080"

            # Session status
            r = self._run("--project", path, "session", "status")
            assert r.returncode == 0
            assert "project_open: True" in r.stdout
        finally:
            os.unlink(path)


# ── True Backend E2E Tests (requires melt installed) ─────────────

class TestMeltBackend:
    """Tests that verify melt is installed and accessible."""

    def test_melt_is_installed(self):
        from cli_anything.shotcut.utils.melt_backend import find_melt
        path = find_melt()
        assert os.path.exists(path)
        print(f"\n  melt binary: {path}")

    def test_melt_version(self):
        from cli_anything.shotcut.utils.melt_backend import get_melt_version
        version = get_melt_version()
        assert version  # Non-empty
        print(f"\n  melt version: {version}")


class TestMeltRenderE2E:
    """True E2E tests: render videos using melt."""

    def test_render_color_bars_mp4(self):
        """Render a simple color bars video to MP4."""
        from cli_anything.shotcut.utils.melt_backend import render_color_bars

        with tempfile.TemporaryDirectory() as tmp_dir:
            output = os.path.join(tmp_dir, "test.mp4")
            result = render_color_bars(output, duration=2, width=320, height=240)

            assert os.path.exists(result["output"])
            assert result["file_size"] > 0
            assert result["method"] == "melt"
            print(f"\n  Color bars MP4: {result['output']} ({result['file_size']:,} bytes)")

    def test_render_mlt_xml_file(self):
        """Generate an MLT XML and render it with melt."""
        from cli_anything.shotcut.utils.melt_backend import find_melt

        melt = find_melt()

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Write a simple MLT XML that uses built-in producers
            mlt_content = '''<?xml version="1.0" encoding="utf-8"?>
<mlt LC_NUMERIC="C" version="7.0.0" root="/tmp" profile="atsc_720p_25">
  <profile description="HD 720p 25fps" width="320" height="240" progressive="1"
           sample_aspect_num="1" sample_aspect_den="1"
           display_aspect_num="4" display_aspect_den="3"
           frame_rate_num="25" frame_rate_den="1" colorspace="709"/>
  <producer id="producer0" in="0" out="49">
    <property name="resource">color:blue</property>
    <property name="mlt_service">color</property>
  </producer>
  <producer id="producer1" in="0" out="49">
    <property name="resource">color:red</property>
    <property name="mlt_service">color</property>
  </producer>
  <playlist id="playlist0">
    <entry producer="producer0" in="0" out="49"/>
    <entry producer="producer1" in="0" out="49"/>
  </playlist>
  <tractor id="tractor0" in="0" out="99">
    <track producer="playlist0"/>
  </tractor>
</mlt>'''
            mlt_path = os.path.join(tmp_dir, "test.mlt")
            output_path = os.path.join(tmp_dir, "output.mp4")

            with open(mlt_path, 'w') as f:
                f.write(mlt_content)

            import subprocess
            cmd = [
                melt, mlt_path,
                "-consumer", f"avformat:{output_path}",
                "vcodec=libx264", "acodec=aac",
                "ar=48000", "channels=2",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            assert result.returncode == 0, f"melt failed: {result.stderr[-500:]}"

            assert os.path.exists(output_path)
            size = os.path.getsize(output_path)
            assert size > 0
            print(f"\n  MLT XML render: {output_path} ({size:,} bytes)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
