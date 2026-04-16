"""Tests for the Shotcut CLI core modules."""

import os
import sys
import json
import tempfile
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.shotcut.core.session import Session
from cli_anything.shotcut.core import project as proj_mod
from cli_anything.shotcut.core import timeline as tl_mod
from cli_anything.shotcut.core import filters as filt_mod
from cli_anything.shotcut.core import media as media_mod
from cli_anything.shotcut.core import export as export_mod
from cli_anything.shotcut.core import transitions as trans_mod
from cli_anything.shotcut.core import compositing as comp_mod
from cli_anything.shotcut.utils.time import (
    timecode_to_frames, frames_to_timecode, parse_time_input,
    frames_to_seconds, seconds_to_frames,
)
from cli_anything.shotcut.utils.mlt_xml import (
    create_blank_project, mlt_to_string, parse_mlt, write_mlt,
    get_property, set_property, get_main_tractor, get_tractor_tracks,
    get_all_producers, get_playlist_entries, find_element_by_id,
    add_filter_to_element,
)


# ============================================================================
# Timecode utilities
# ============================================================================

class TestTimecode:
    def test_plain_frame_number(self):
        assert timecode_to_frames("100") == 100

    def test_hh_mm_ss_mmm(self):
        # At 30000/1001 fps (≈29.97)
        frames = timecode_to_frames("00:00:01.000")
        # Should be approximately 30 frames
        assert 29 <= frames <= 30

    def test_hh_mm_ss(self):
        frames = timecode_to_frames("00:01:00")
        fps = 30000 / 1001
        expected = int(60 * fps)
        assert abs(frames - expected) <= 1

    def test_seconds_decimal(self):
        frames = timecode_to_frames("2.5")
        fps = 30000 / 1001
        expected = int(2.5 * fps)
        assert abs(frames - expected) <= 1

    def test_roundtrip(self):
        for original_frames in [0, 1, 30, 900, 1800, 54000]:
            tc = frames_to_timecode(original_frames)
            back = timecode_to_frames(tc)
            assert abs(back - original_frames) <= 1, \
                f"Roundtrip failed: {original_frames} → {tc} → {back}"

    def test_invalid_timecode(self):
        with pytest.raises(ValueError):
            timecode_to_frames("invalid")

    def test_negative_frames(self):
        tc = frames_to_timecode(-5)
        assert tc == "00:00:00.000"

    def test_frames_to_seconds(self):
        secs = frames_to_seconds(30, 30000, 1001)
        assert abs(secs - 1.001) < 0.01

    def test_seconds_to_frames(self):
        frames = seconds_to_frames(1.0, 30000, 1001)
        assert 29 <= frames <= 30


# ============================================================================
# MLT XML utilities
# ============================================================================

class TestMltXml:
    def test_create_blank_project(self):
        profile = {
            "width": "1920", "height": "1080",
            "frame_rate_num": "30000", "frame_rate_den": "1001",
            "sample_aspect_num": "1", "sample_aspect_den": "1",
            "display_aspect_num": "16", "display_aspect_den": "9",
            "progressive": "1", "colorspace": "709",
        }
        root = create_blank_project(profile)
        assert root.tag == "mlt"
        assert root.get("title") == "Shotcut"

        # Should have a profile
        prof = root.find("profile")
        assert prof is not None
        assert prof.get("width") == "1920"

        # Should have a main tractor
        tractor = get_main_tractor(root)
        assert tractor is not None

    def test_write_and_parse(self):
        profile = {
            "width": "1280", "height": "720",
            "frame_rate_num": "24000", "frame_rate_den": "1001",
            "sample_aspect_num": "1", "sample_aspect_den": "1",
            "display_aspect_num": "16", "display_aspect_den": "9",
            "progressive": "1", "colorspace": "709",
        }
        root = create_blank_project(profile)

        with tempfile.NamedTemporaryFile(suffix=".mlt", delete=False) as f:
            tmpfile = f.name

        try:
            write_mlt(root, tmpfile)
            parsed = parse_mlt(tmpfile)
            assert parsed.tag == "mlt"
            prof = parsed.find("profile")
            assert prof.get("width") == "1280"
        finally:
            os.unlink(tmpfile)

    def test_properties(self):
        from lxml import etree
        elem = etree.Element("producer")
        set_property(elem, "resource", "/test/video.mp4")
        assert get_property(elem, "resource") == "/test/video.mp4"
        assert get_property(elem, "nonexistent") is None
        assert get_property(elem, "nonexistent", "default") == "default"

    def test_mlt_to_string(self):
        profile = {"width": "1920", "height": "1080",
                    "frame_rate_num": "30000", "frame_rate_den": "1001",
                    "sample_aspect_num": "1", "sample_aspect_den": "1",
                    "display_aspect_num": "16", "display_aspect_den": "9",
                    "progressive": "1", "colorspace": "709"}
        root = create_blank_project(profile)
        xml_str = mlt_to_string(root)
        assert "<?xml" in xml_str
        assert "<mlt" in xml_str
        assert "Shotcut" in xml_str


# ============================================================================
# Session
# ============================================================================

class TestSession:
    def test_new_session(self):
        s = Session("test_session_1")
        assert s.session_id == "test_session_1"
        assert not s.is_open
        assert not s.is_modified

    def test_new_project(self):
        s = Session()
        s.new_project()
        assert s.is_open
        assert not s.is_modified

    def test_save_and_open(self):
        s = Session()
        s.new_project()

        with tempfile.NamedTemporaryFile(suffix=".mlt", delete=False) as f:
            tmpfile = f.name

        try:
            s.save_project(tmpfile)
            assert not s.is_modified

            s2 = Session()
            s2.open_project(tmpfile)
            assert s2.is_open
            assert s2.project_path == tmpfile
        finally:
            os.unlink(tmpfile)

    def test_undo_redo(self):
        s = Session()
        s.new_project()

        # Can't undo with no changes
        assert not s.undo()

        # Make a change
        s.checkpoint()
        tractor = s.get_main_tractor()
        from cli_anything.shotcut.utils.mlt_xml import add_track_to_tractor
        add_track_to_tractor(s.root, tractor, "video")

        assert s.is_modified

        # Undo should work
        tracks_before = len(get_tractor_tracks(s.get_main_tractor()))
        assert s.undo()
        tracks_after = len(get_tractor_tracks(s.get_main_tractor()))
        assert tracks_after < tracks_before

        # Redo should work
        assert s.redo()
        tracks_redone = len(get_tractor_tracks(s.get_main_tractor()))
        assert tracks_redone == tracks_before

    def test_open_nonexistent(self):
        s = Session()
        with pytest.raises(FileNotFoundError):
            s.open_project("/nonexistent/path.mlt")

    def test_save_without_project(self):
        s = Session()
        with pytest.raises(RuntimeError):
            s.save_project("/tmp/test.mlt")

    def test_status(self):
        s = Session()
        status = s.status()
        assert status["project_open"] is False

        s.new_project()
        status = s.status()
        assert status["project_open"] is True
        assert "profile" in status


# ============================================================================
# Project module
# ============================================================================

class TestProject:
    def test_new_project(self):
        s = Session()
        result = proj_mod.new_project(s, "hd1080p30")
        assert result["profile"] == "hd1080p30"
        assert s.is_open

    def test_new_project_invalid_profile(self):
        s = Session()
        with pytest.raises(ValueError):
            proj_mod.new_project(s, "invalid_profile")

    def test_project_info(self):
        s = Session()
        proj_mod.new_project(s, "hd1080p30")
        info = proj_mod.project_info(s)
        assert "profile" in info
        assert "tracks" in info
        assert "media_clips" in info

    def test_list_profiles(self):
        profiles = proj_mod.list_profiles()
        assert "hd1080p30" in profiles
        assert "4k30" in profiles

    def test_save_project(self):
        s = Session()
        proj_mod.new_project(s)
        with tempfile.NamedTemporaryFile(suffix=".mlt", delete=False) as f:
            tmpfile = f.name
        try:
            result = proj_mod.save_project(s, tmpfile)
            assert result["path"] == tmpfile
            assert os.path.isfile(tmpfile)
        finally:
            os.unlink(tmpfile)

    def test_open_and_info(self):
        s = Session()
        proj_mod.new_project(s, "hd720p30")

        with tempfile.NamedTemporaryFile(suffix=".mlt", delete=False) as f:
            tmpfile = f.name
        try:
            proj_mod.save_project(s, tmpfile)

            s2 = Session()
            result = proj_mod.open_project(s2, tmpfile)
            assert result["path"] == tmpfile
        finally:
            os.unlink(tmpfile)


# ============================================================================
# Timeline module
# ============================================================================

class TestTimeline:
    def _make_session(self):
        s = Session()
        proj_mod.new_project(s, "hd1080p30")
        return s

    def test_list_tracks_initial(self):
        s = self._make_session()
        tracks = tl_mod.list_tracks(s)
        # Should have at least the background track
        assert len(tracks) >= 1

    def test_add_video_track(self):
        s = self._make_session()
        initial = len(tl_mod.list_tracks(s))
        result = tl_mod.add_track(s, "video", "V1")
        assert result["type"] == "video"
        assert len(tl_mod.list_tracks(s)) == initial + 1

    def test_add_audio_track(self):
        s = self._make_session()
        initial = len(tl_mod.list_tracks(s))
        result = tl_mod.add_track(s, "audio", "A1")
        assert result["type"] == "audio"
        assert len(tl_mod.list_tracks(s)) == initial + 1

    def test_add_invalid_track_type(self):
        s = self._make_session()
        with pytest.raises(ValueError):
            tl_mod.add_track(s, "invalid")

    def test_remove_track(self):
        s = self._make_session()
        tl_mod.add_track(s, "video", "V1")
        tracks = tl_mod.list_tracks(s)
        count_before = len(tracks)

        # Remove the last added track
        tl_mod.remove_track(s, count_before - 1)
        assert len(tl_mod.list_tracks(s)) == count_before - 1

    def test_remove_background_track_fails(self):
        s = self._make_session()
        with pytest.raises(IndexError):
            tl_mod.remove_track(s, 0)

    def test_add_clip_file_not_found(self):
        s = self._make_session()
        tl_mod.add_track(s, "video")
        with pytest.raises(FileNotFoundError):
            tl_mod.add_clip(s, "/nonexistent/video.mp4", 1)

    def test_add_and_list_clip(self):
        s = self._make_session()
        tl_mod.add_track(s, "video")

        # Create a dummy file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"dummy")
            tmpfile = f.name

        try:
            result = tl_mod.add_clip(s, tmpfile, 1,
                                     in_point="00:00:00.000",
                                     out_point="00:00:05.000")
            assert result["track_index"] == 1

            clips = tl_mod.list_clips(s, 1)
            assert len([c for c in clips if c.get("clip_index") is not None]) == 1
        finally:
            os.unlink(tmpfile)

    def test_remove_clip(self):
        s = self._make_session()
        tl_mod.add_track(s, "video")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"dummy")
            tmpfile = f.name

        try:
            tl_mod.add_clip(s, tmpfile, 1,
                            in_point="00:00:00.000", out_point="00:00:05.000")
            result = tl_mod.remove_clip(s, 1, 0)
            assert result["action"] == "remove_clip"

            clips = tl_mod.list_clips(s, 1)
            clip_entries = [c for c in clips if c.get("clip_index") is not None]
            assert len(clip_entries) == 0
        finally:
            os.unlink(tmpfile)

    def test_trim_clip(self):
        s = self._make_session()
        tl_mod.add_track(s, "video")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"dummy")
            tmpfile = f.name

        try:
            tl_mod.add_clip(s, tmpfile, 1,
                            in_point="00:00:00.000", out_point="00:00:10.000")
            result = tl_mod.trim_clip(s, 1, 0,
                                      in_point="00:00:02.000",
                                      out_point="00:00:08.000")
            assert result["new_in"] == "00:00:02.000"
            assert result["new_out"] == "00:00:08.000"
        finally:
            os.unlink(tmpfile)

    def test_split_clip(self):
        s = self._make_session()
        tl_mod.add_track(s, "video")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"dummy")
            tmpfile = f.name

        try:
            tl_mod.add_clip(s, tmpfile, 1,
                            in_point="00:00:00.000", out_point="00:00:10.000")
            result = tl_mod.split_clip(s, 1, 0, "00:00:05.000")
            assert result["action"] == "split_clip"
            assert result["first_clip"]["out"] == "00:00:05.000"
            assert result["second_clip"]["in"] == "00:00:05.000"

            # Should now have 2 clips
            clips = tl_mod.list_clips(s, 1)
            clip_entries = [c for c in clips if c.get("clip_index") is not None]
            assert len(clip_entries) == 2
        finally:
            os.unlink(tmpfile)

    def test_move_clip(self):
        s = self._make_session()
        tl_mod.add_track(s, "video", "V1")
        tl_mod.add_track(s, "video", "V2")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"dummy")
            tmpfile = f.name

        try:
            tl_mod.add_clip(s, tmpfile, 1,
                            in_point="00:00:00.000", out_point="00:00:05.000")

            # Move from track 1 to track 2
            result = tl_mod.move_clip(s, 1, 0, 2)
            assert result["action"] == "move_clip"

            # Track 1 should be empty, track 2 should have the clip
            clips1 = [c for c in tl_mod.list_clips(s, 1) if c.get("clip_index") is not None]
            clips2 = [c for c in tl_mod.list_clips(s, 2) if c.get("clip_index") is not None]
            assert len(clips1) == 0
            assert len(clips2) == 1
        finally:
            os.unlink(tmpfile)

    def test_set_track_name(self):
        s = self._make_session()
        tl_mod.add_track(s, "video")
        result = tl_mod.set_track_name(s, 1, "My Track")
        assert result["name"] == "My Track"

    def test_mute_unmute(self):
        s = self._make_session()
        tl_mod.add_track(s, "audio")
        tracks = tl_mod.list_tracks(s)
        audio_idx = len(tracks) - 1

        result = tl_mod.set_track_mute(s, audio_idx, True)
        assert result["mute"] is True

        result = tl_mod.set_track_mute(s, audio_idx, False)
        assert result["mute"] is False

    def test_show_timeline(self):
        s = self._make_session()
        tl_mod.add_track(s, "video", "V1")
        result = tl_mod.show_timeline(s)
        assert "tracks" in result
        assert "fps_num" in result

    def test_add_blank(self):
        s = self._make_session()
        tl_mod.add_track(s, "video")
        result = tl_mod.add_blank(s, 1, "00:00:02.000")
        assert result["action"] == "add_blank"

    def test_undo_add_track(self):
        s = self._make_session()
        initial = len(tl_mod.list_tracks(s))
        tl_mod.add_track(s, "video")
        assert len(tl_mod.list_tracks(s)) == initial + 1

        s.undo()
        assert len(tl_mod.list_tracks(s)) == initial


# ============================================================================
# Filters module
# ============================================================================

class TestFilters:
    def _make_session_with_clip(self):
        s = Session()
        proj_mod.new_project(s, "hd1080p30")
        tl_mod.add_track(s, "video")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"dummy")
            tmpfile = f.name

        tl_mod.add_clip(s, tmpfile, 1,
                        in_point="00:00:00.000", out_point="00:00:05.000")
        return s, tmpfile

    def test_list_available_filters(self):
        result = filt_mod.list_available_filters()
        assert len(result) > 0
        names = [f["name"] for f in result]
        assert "brightness" in names
        assert "volume" in names

    def test_list_by_category(self):
        video = filt_mod.list_available_filters("video")
        audio = filt_mod.list_available_filters("audio")
        assert all(f["category"] == "video" for f in video)
        assert all(f["category"] == "audio" for f in audio)

    def test_get_filter_info(self):
        info = filt_mod.get_filter_info("brightness")
        assert info["service"] == "brightness"
        assert "params" in info

    def test_get_unknown_filter(self):
        with pytest.raises(ValueError):
            filt_mod.get_filter_info("nonexistent_filter")

    def test_add_filter_to_clip(self):
        s, tmpfile = self._make_session_with_clip()
        try:
            result = filt_mod.add_filter(s, "brightness", track_index=1, clip_index=0,
                                         params={"level": "1.5"})
            assert result["service"] == "brightness"
            assert result["params"]["level"] == "1.5"

            # Verify filter is there
            filters = filt_mod.list_filters(s, track_index=1, clip_index=0)
            assert len(filters) == 1
            assert filters[0]["service"] == "brightness"
        finally:
            os.unlink(tmpfile)

    def test_add_filter_to_track(self):
        s, tmpfile = self._make_session_with_clip()
        try:
            result = filt_mod.add_filter(s, "volume", track_index=1)
            assert result["target"] == "track 1"

            filters = filt_mod.list_filters(s, track_index=1)
            assert len(filters) >= 1
        finally:
            os.unlink(tmpfile)

    def test_add_global_filter(self):
        s = Session()
        proj_mod.new_project(s)
        result = filt_mod.add_filter(s, "brightness")
        assert result["target"] == "global"

    def test_remove_filter(self):
        s, tmpfile = self._make_session_with_clip()
        try:
            filt_mod.add_filter(s, "brightness", track_index=1, clip_index=0)
            result = filt_mod.remove_filter(s, 0, track_index=1, clip_index=0)
            assert result["action"] == "remove_filter"

            filters = filt_mod.list_filters(s, track_index=1, clip_index=0)
            assert len(filters) == 0
        finally:
            os.unlink(tmpfile)

    def test_set_filter_param(self):
        s, tmpfile = self._make_session_with_clip()
        try:
            filt_mod.add_filter(s, "brightness", track_index=1, clip_index=0)
            result = filt_mod.set_filter_param(s, 0, "level", "0.5",
                                                track_index=1, clip_index=0)
            assert result["new_value"] == "0.5"
        finally:
            os.unlink(tmpfile)

    def test_undo_add_filter(self):
        s, tmpfile = self._make_session_with_clip()
        try:
            filt_mod.add_filter(s, "brightness", track_index=1, clip_index=0)
            assert len(filt_mod.list_filters(s, track_index=1, clip_index=0)) == 1

            s.undo()
            assert len(filt_mod.list_filters(s, track_index=1, clip_index=0)) == 0
        finally:
            os.unlink(tmpfile)


# ============================================================================
# Media module
# ============================================================================

class TestMedia:
    def test_probe_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            media_mod.probe_media("/nonexistent/file.mp4")

    def test_probe_basic(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"not a real video")
            tmpfile = f.name
        try:
            result = media_mod.probe_media(tmpfile)
            assert result["filename"] == os.path.basename(tmpfile)
            assert result["size_bytes"] > 0
        finally:
            os.unlink(tmpfile)

    def test_list_media_empty(self):
        s = Session()
        proj_mod.new_project(s)
        result = media_mod.list_media(s)
        assert result == []

    def test_list_media_with_clip(self):
        s = Session()
        proj_mod.new_project(s)
        tl_mod.add_track(s, "video")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"dummy")
            tmpfile = f.name
        try:
            tl_mod.add_clip(s, tmpfile, 1,
                            in_point="00:00:00.000", out_point="00:00:05.000")
            result = media_mod.list_media(s)
            assert len(result) >= 1
            assert any(tmpfile in m["resource"] for m in result)
        finally:
            os.unlink(tmpfile)

    def test_check_media_files(self):
        s = Session()
        proj_mod.new_project(s)
        result = media_mod.check_media_files(s)
        assert result["total"] == 0
        assert result["all_present"] is True


# ============================================================================
# Export module
# ============================================================================

class TestExport:
    def test_list_presets(self):
        result = export_mod.list_presets()
        assert len(result) > 0
        names = [p["name"] for p in result]
        assert "default" in names
        assert "h264-high" in names

    def test_get_preset_info(self):
        info = export_mod.get_preset_info("default")
        assert info["vcodec"] == "libx264"
        assert info["acodec"] == "aac"

    def test_unknown_preset(self):
        with pytest.raises(ValueError):
            export_mod.get_preset_info("nonexistent")

    def test_render_no_project(self):
        s = Session()
        with pytest.raises(RuntimeError):
            export_mod.render(s, "/tmp/output.mp4")

    def test_render_no_overwrite(self):
        s = Session()
        proj_mod.new_project(s)
        tl_mod.add_track(s, "video")

        # Create existing output file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"existing")
            tmpfile = f.name
        try:
            with pytest.raises(FileExistsError):
                export_mod.render(s, tmpfile)
        finally:
            os.unlink(tmpfile)


# ============================================================================
# Integration: full workflow
# ============================================================================

class TestIntegration:
    def test_full_workflow(self):
        """Test a complete editing workflow: create project, add tracks,
        add clips, apply filters, save, reopen, verify."""
        s = Session()

        # 1. Create project
        proj_mod.new_project(s, "hd1080p30")
        assert s.is_open

        # 2. Add tracks
        tl_mod.add_track(s, "video", "V1")
        tl_mod.add_track(s, "audio", "A1")
        tracks = tl_mod.list_tracks(s)
        assert len(tracks) >= 3  # background + V1 + A1

        # 3. Create dummy media files
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"video1")
            video1 = f.name
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"video2")
            video2 = f.name

        try:
            # 4. Add clips
            tl_mod.add_clip(s, video1, 1,
                            in_point="00:00:00.000", out_point="00:00:05.000",
                            caption="Intro")
            tl_mod.add_clip(s, video2, 1,
                            in_point="00:00:00.000", out_point="00:00:10.000",
                            caption="Main")

            clips = tl_mod.list_clips(s, 1)
            clip_entries = [c for c in clips if c.get("clip_index") is not None]
            assert len(clip_entries) == 2

            # 5. Apply filter to first clip
            filt_mod.add_filter(s, "brightness", track_index=1, clip_index=0,
                                params={"level": "1.2"})

            # 6. Trim second clip
            tl_mod.trim_clip(s, 1, 1, in_point="00:00:02.000")

            # 7. Save
            with tempfile.NamedTemporaryFile(suffix=".mlt", delete=False) as f:
                project_file = f.name
            proj_mod.save_project(s, project_file)
            assert os.path.isfile(project_file)

            # 8. Reopen and verify
            s2 = Session()
            proj_mod.open_project(s2, project_file)
            info = proj_mod.project_info(s2)
            assert info["profile"]["width"] == "1920"
            assert len(info["media_clips"]) >= 2

            # 9. Verify undo works
            tl_mod.add_track(s, "video", "V2")
            s.undo()
            # Track count should be back to before

            os.unlink(project_file)
        finally:
            os.unlink(video1)
            os.unlink(video2)

    def test_save_load_roundtrip_preserves_filters(self):
        """Verify that filters survive save/load."""
        s = Session()
        proj_mod.new_project(s)
        tl_mod.add_track(s, "video")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"test")
            tmpfile = f.name

        try:
            tl_mod.add_clip(s, tmpfile, 1,
                            in_point="00:00:00.000", out_point="00:00:05.000")
            filt_mod.add_filter(s, "brightness", track_index=1, clip_index=0,
                                params={"level": "0.8"})

            with tempfile.NamedTemporaryFile(suffix=".mlt", delete=False) as f:
                project_file = f.name

            proj_mod.save_project(s, project_file)

            # Reopen
            s2 = Session()
            proj_mod.open_project(s2, project_file)

            # Find the clip and check its filter
            from cli_anything.shotcut.utils.mlt_xml import get_all_producers, get_property
            producers = get_all_producers(s2.root)
            found_filter = False
            for prod in producers:
                for filt in prod.findall("filter"):
                    if get_property(filt, "mlt_service") == "brightness":
                        assert get_property(filt, "level") == "0.8"
                        found_filter = True
            assert found_filter, "Filter not found after save/load"

            os.unlink(project_file)
        finally:
            os.unlink(tmpfile)


# ============================================================================
# Transitions module
# ============================================================================

class TestTransitions:
    def _make_session_with_two_tracks(self):
        """Create a session with two video tracks and clips for transition testing."""
        s = Session()
        proj_mod.new_project(s, "hd1080p30")
        tl_mod.add_track(s, "video")
        tl_mod.add_track(s, "video")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"dummy")
            tmpfile = f.name

        tl_mod.add_clip(s, tmpfile, 1,
                        in_point="00:00:00.000", out_point="00:00:05.000")
        tl_mod.add_clip(s, tmpfile, 2,
                        in_point="00:00:00.000", out_point="00:00:05.000")
        return s, tmpfile

    def test_list_available_transitions(self):
        result = trans_mod.list_available_transitions()
        assert len(result) >= 10
        names = [t["name"] for t in result]
        assert "dissolve" in names
        assert "wipe-left" in names
        assert "crossfade" in names

    def test_list_by_category_video(self):
        result = trans_mod.list_available_transitions(category="video")
        for t in result:
            assert t["category"] == "video"
        names = [t["name"] for t in result]
        assert "dissolve" in names
        assert "crossfade" not in names

    def test_list_by_category_audio(self):
        result = trans_mod.list_available_transitions(category="audio")
        for t in result:
            assert t["category"] == "audio"
        names = [t["name"] for t in result]
        assert "crossfade" in names

    def test_get_transition_info(self):
        info = trans_mod.get_transition_info("dissolve")
        assert info["name"] == "dissolve"
        assert info["service"] == "luma"
        assert "params" in info

    def test_get_transition_info_invalid(self):
        with pytest.raises(ValueError):
            trans_mod.get_transition_info("nonexistent_transition")

    def test_add_transition(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            result = trans_mod.add_transition(
                s, "dissolve", track_a=1, track_b=2,
                in_point="00:00:03.000", out_point="00:00:05.000")
            assert result["action"] == "add_transition"
            assert result["transition_name"] == "dissolve"
            assert result["service"] == "luma"
            assert result["track_a"] == 1
            assert result["track_b"] == 2
        finally:
            os.unlink(tmpfile)

    def test_add_transition_with_params(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            result = trans_mod.add_transition(
                s, "dissolve", track_a=1, track_b=2,
                params={"softness": "0.5"})
            assert result["params"]["softness"] == "0.5"
        finally:
            os.unlink(tmpfile)

    def test_add_wipe_transition(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            result = trans_mod.add_transition(
                s, "wipe-left", track_a=1, track_b=2)
            assert result["service"] == "luma"
            assert result["params"]["resource"] == "%luma01.pgm"
        finally:
            os.unlink(tmpfile)

    def test_add_transition_invalid_track(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            with pytest.raises(IndexError):
                trans_mod.add_transition(s, "dissolve", track_a=1, track_b=99)
        finally:
            os.unlink(tmpfile)

    def test_add_raw_service_transition(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            result = trans_mod.add_transition(
                s, "luma", track_a=1, track_b=2,
                params={"softness": "0.3"})
            assert result["service"] == "luma"
        finally:
            os.unlink(tmpfile)

    def test_list_transitions_empty(self):
        s = Session()
        proj_mod.new_project(s, "hd1080p30")
        result = trans_mod.list_transitions(s)
        assert result == []

    def test_list_transitions_after_add(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            baseline = len(trans_mod.list_transitions(s))
            trans_mod.add_transition(s, "dissolve", track_a=1, track_b=2)
            result = trans_mod.list_transitions(s)
            assert len(result) == baseline + 1
            # The last one should be our dissolve
            assert result[-1]["service"] == "luma"
        finally:
            os.unlink(tmpfile)

    def test_remove_transition(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            baseline = len(trans_mod.list_transitions(s))
            trans_mod.add_transition(s, "dissolve", track_a=1, track_b=2)
            assert len(trans_mod.list_transitions(s)) == baseline + 1

            result = trans_mod.remove_transition(s, baseline)  # remove the added one
            assert result["action"] == "remove_transition"
            assert len(trans_mod.list_transitions(s)) == baseline
        finally:
            os.unlink(tmpfile)

    def test_remove_transition_invalid_index(self):
        s = Session()
        proj_mod.new_project(s, "hd1080p30")
        with pytest.raises(IndexError):
            trans_mod.remove_transition(s, 0)

    def test_set_transition_param(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            trans_mod.add_transition(s, "dissolve", track_a=1, track_b=2)
            result = trans_mod.set_transition_param(s, 0, "softness", "0.8")
            assert result["action"] == "set_transition_param"
            assert result["new_value"] == "0.8"
        finally:
            os.unlink(tmpfile)

    def test_undo_add_transition(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            baseline = len(trans_mod.list_transitions(s))
            trans_mod.add_transition(s, "dissolve", track_a=1, track_b=2)
            assert len(trans_mod.list_transitions(s)) == baseline + 1
            s.undo()
            assert len(trans_mod.list_transitions(s)) == baseline
        finally:
            os.unlink(tmpfile)

    def test_multiple_transitions(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            baseline = len(trans_mod.list_transitions(s))
            trans_mod.add_transition(s, "dissolve", track_a=1, track_b=2,
                                     in_point="00:00:03.000", out_point="00:00:05.000")
            trans_mod.add_transition(s, "wipe-left", track_a=1, track_b=2,
                                     in_point="00:00:08.000", out_point="00:00:10.000")
            result = trans_mod.list_transitions(s)
            assert len(result) == baseline + 2
        finally:
            os.unlink(tmpfile)


# ============================================================================
# Compositing module
# ============================================================================

class TestCompositing:
    def _make_session_with_two_tracks(self):
        s = Session()
        proj_mod.new_project(s, "hd1080p30")
        tl_mod.add_track(s, "video")
        tl_mod.add_track(s, "video")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"dummy")
            tmpfile = f.name

        tl_mod.add_clip(s, tmpfile, 1,
                        in_point="00:00:00.000", out_point="00:00:05.000")
        tl_mod.add_clip(s, tmpfile, 2,
                        in_point="00:00:00.000", out_point="00:00:05.000")
        return s, tmpfile

    def test_list_blend_modes(self):
        result = comp_mod.list_blend_modes()
        assert len(result) >= 18
        names = [m["name"] for m in result]
        assert "normal" in names
        assert "multiply" in names
        assert "screen" in names
        assert "overlay" in names

    def test_set_track_blend_mode(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            result = comp_mod.set_track_blend_mode(s, track_index=2, blend_mode="multiply")
            assert result["action"] == "set_blend_mode"
            assert result["blend_mode"] == "multiply"
            assert result["track_index"] == 2
        finally:
            os.unlink(tmpfile)

    def test_set_blend_mode_invalid(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            with pytest.raises(ValueError):
                comp_mod.set_track_blend_mode(s, 2, "nonexistent_mode")
        finally:
            os.unlink(tmpfile)

    def test_set_blend_mode_background_track(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            with pytest.raises(ValueError):
                comp_mod.set_track_blend_mode(s, 0, "multiply")
        finally:
            os.unlink(tmpfile)

    def test_get_track_blend_mode_default(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            result = comp_mod.get_track_blend_mode(s, track_index=2)
            assert result["blend_mode"] == "normal"
        finally:
            os.unlink(tmpfile)

    def test_get_track_blend_mode_after_set(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            comp_mod.set_track_blend_mode(s, 2, "screen")
            result = comp_mod.get_track_blend_mode(s, 2)
            assert result["blend_mode"] == "screen"
        finally:
            os.unlink(tmpfile)

    def test_set_track_opacity(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            result = comp_mod.set_track_opacity(s, track_index=1, opacity=0.5)
            assert result["action"] == "set_track_opacity"
            assert result["opacity"] == 0.5
        finally:
            os.unlink(tmpfile)

    def test_set_track_opacity_invalid_range(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            with pytest.raises(ValueError):
                comp_mod.set_track_opacity(s, 1, 1.5)
            with pytest.raises(ValueError):
                comp_mod.set_track_opacity(s, 1, -0.1)
        finally:
            os.unlink(tmpfile)

    def test_set_track_opacity_invalid_index(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            with pytest.raises(IndexError):
                comp_mod.set_track_opacity(s, 99, 0.5)
        finally:
            os.unlink(tmpfile)

    def test_set_track_opacity_update_existing(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            comp_mod.set_track_opacity(s, 1, 0.5)
            result = comp_mod.set_track_opacity(s, 1, 0.8)
            assert result["opacity"] == 0.8
        finally:
            os.unlink(tmpfile)

    def test_pip_position(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            result = comp_mod.pip_position(
                s, track_index=2, clip_index=0,
                x="10%", y="10%", width="40%", height="40%", opacity=0.9)
            assert result["action"] == "pip_position"
            assert "10%/10%:40%x40%:90" == result["geometry"]
        finally:
            os.unlink(tmpfile)

    def test_pip_position_defaults(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            result = comp_mod.pip_position(s, track_index=2, clip_index=0)
            assert result["geometry"] == "0/0:100%x100%:100"
        finally:
            os.unlink(tmpfile)

    def test_pip_position_invalid_track(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            with pytest.raises(IndexError):
                comp_mod.pip_position(s, track_index=99, clip_index=0)
        finally:
            os.unlink(tmpfile)

    def test_pip_position_invalid_clip(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            with pytest.raises(IndexError):
                comp_mod.pip_position(s, track_index=2, clip_index=99)
        finally:
            os.unlink(tmpfile)

    def test_pip_update_existing(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            comp_mod.pip_position(s, 2, 0, x="10%", y="10%",
                                  width="40%", height="40%")
            result = comp_mod.pip_position(s, 2, 0, x="20%", y="20%",
                                           width="50%", height="50%")
            assert "20%/20%:50%x50%:100" == result["geometry"]
        finally:
            os.unlink(tmpfile)

    def test_undo_set_blend_mode(self):
        s, tmpfile = self._make_session_with_two_tracks()
        try:
            comp_mod.set_track_blend_mode(s, 2, "multiply")
            assert comp_mod.get_track_blend_mode(s, 2)["blend_mode"] == "multiply"
            s.undo()
            assert comp_mod.get_track_blend_mode(s, 2)["blend_mode"] == "normal"
        finally:
            os.unlink(tmpfile)


# ============================================================================
# Expanded filters (new categories)
# ============================================================================

class TestExpandedFilters:
    def _make_session_with_clip(self):
        s = Session()
        proj_mod.new_project(s, "hd1080p30")
        tl_mod.add_track(s, "video")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"dummy")
            tmpfile = f.name

        tl_mod.add_clip(s, tmpfile, 1,
                        in_point="00:00:00.000", out_point="00:00:05.000")
        return s, tmpfile

    def test_filter_categories(self):
        result = filt_mod.list_available_filters()
        categories = set(f["category"] for f in result)
        assert "color" in categories or "video" in categories
        assert "audio" in categories

    def test_chroma_key_filter_exists(self):
        result = filt_mod.list_available_filters()
        names = [f["name"] for f in result]
        assert "chroma-key" in names or "chroma-key-advanced" in names

    def test_color_grading_filters_exist(self):
        result = filt_mod.list_available_filters()
        names = [f["name"] for f in result]
        # At least some color grading filters should be present
        color_filters = [n for n in names if n in
                         ("color-grading", "levels", "white-balance",
                          "contrast", "gamma", "vibrance", "invert",
                          "grayscale", "threshold", "posterize")]
        assert len(color_filters) >= 3

    def test_distortion_filters_exist(self):
        result = filt_mod.list_available_filters()
        names = [f["name"] for f in result]
        fx_filters = [n for n in names if n in
                      ("sharpen", "vignette", "grain", "pixelize",
                       "wave", "oldfilm", "vertigo")]
        assert len(fx_filters) >= 2

    def test_transform_filters_exist(self):
        result = filt_mod.list_available_filters()
        names = [f["name"] for f in result]
        transform_filters = [n for n in names if n in
                             ("size-position", "rotate-scale",
                              "flip-horizontal", "flip-vertical")]
        assert len(transform_filters) >= 2

    def test_audio_filters_exist(self):
        result = filt_mod.list_available_filters()
        names = [f["name"] for f in result]
        audio_filters = [n for n in names if n in
                         ("equalizer", "compressor", "reverb",
                          "normalize-audio", "lowpass", "highpass",
                          "delay", "mute", "balance")]
        assert len(audio_filters) >= 3

    def test_add_sharpen_filter(self):
        s, tmpfile = self._make_session_with_clip()
        try:
            result = filt_mod.add_filter(s, "sharpen", track_index=1, clip_index=0)
            assert result["action"] == "add_filter"
            assert result["filter_name"] == "sharpen"
        finally:
            os.unlink(tmpfile)

    def test_add_vignette_filter(self):
        s, tmpfile = self._make_session_with_clip()
        try:
            result = filt_mod.add_filter(s, "vignette", track_index=1, clip_index=0)
            assert result["action"] == "add_filter"
        finally:
            os.unlink(tmpfile)

    def test_add_grayscale_filter(self):
        s, tmpfile = self._make_session_with_clip()
        try:
            result = filt_mod.add_filter(s, "grayscale", track_index=1, clip_index=0)
            assert result["action"] == "add_filter"
        finally:
            os.unlink(tmpfile)

    def test_add_invert_filter(self):
        s, tmpfile = self._make_session_with_clip()
        try:
            result = filt_mod.add_filter(s, "invert", track_index=1, clip_index=0)
            assert result["action"] == "add_filter"
        finally:
            os.unlink(tmpfile)

    def test_total_filter_count(self):
        result = filt_mod.list_available_filters()
        assert len(result) >= 50, f"Expected 50+ filters, got {len(result)}"

    def test_filter_info_has_params(self):
        info = filt_mod.get_filter_info("sharpen")
        assert "params" in info
        assert info["name"] == "sharpen"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
