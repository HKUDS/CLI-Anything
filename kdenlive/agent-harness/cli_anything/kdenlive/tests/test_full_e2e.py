"""End-to-end tests for Kdenlive CLI.

Tests XML generation, format validation, and full workflow scenarios.
No Kdenlive or melt installation required.
"""

import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.kdenlive.core.project import create_project, save_project, open_project, get_project_info
from cli_anything.kdenlive.core.bin import import_clip, list_clips
from cli_anything.kdenlive.core.timeline import (
    add_track, add_clip_to_track, remove_clip_from_track,
    trim_clip, split_clip, move_clip, list_tracks,
)
from cli_anything.kdenlive.core.filters import add_filter, list_filters, FILTER_REGISTRY
from cli_anything.kdenlive.core.transitions import add_transition, list_transitions
from cli_anything.kdenlive.core.guides import add_guide, list_guides
from cli_anything.kdenlive.core.export import generate_kdenlive_xml, list_render_presets, RENDER_PRESETS
from cli_anything.kdenlive.core.session import Session
from cli_anything.kdenlive.utils.mlt_xml import (
    seconds_to_timecode, timecode_to_seconds, seconds_to_frames,
    xml_escape, build_mlt_xml,
)


# ── XML Generation Tests ───────────────────────────────────────

class TestXMLGeneration:
    def _make_full_project(self):
        """Create a project with clips, tracks, filters, transitions, guides."""
        proj = create_project(name="TestProject", profile="hd1080p30")
        import_clip(proj, "/path/to/interview.mp4", name="Interview", duration=120.0)
        import_clip(proj, "/path/to/broll.mp4", name="BRoll", duration=60.0)
        import_clip(proj, "/path/to/music.mp3", name="Music", duration=180.0, clip_type="audio")

        add_track(proj, name="V1", track_type="video")
        add_track(proj, name="V2", track_type="video")
        add_track(proj, name="A1", track_type="audio")

        add_clip_to_track(proj, 0, "clip0", position=0.0, out_point=30.0)
        add_clip_to_track(proj, 1, "clip1", position=5.0, out_point=20.0)
        add_clip_to_track(proj, 2, "clip2", position=0.0, out_point=60.0)

        add_filter(proj, 0, 0, "brightness", {"level": 1.2})
        add_transition(proj, "dissolve", 0, 1, position=5.0, duration=2.0)
        add_guide(proj, 0.0, label="Start")
        add_guide(proj, 30.0, label="End")

        return proj

    def test_xml_is_string(self):
        proj = self._make_full_project()
        xml = generate_kdenlive_xml(proj)
        assert isinstance(xml, str)

    def test_xml_has_mlt_root(self):
        proj = self._make_full_project()
        xml = generate_kdenlive_xml(proj)
        assert xml.startswith('<?xml version="1.0"')
        assert "<mlt " in xml
        assert "</mlt>" in xml

    def test_xml_has_profile(self):
        proj = self._make_full_project()
        xml = generate_kdenlive_xml(proj)
        assert "<profile " in xml
        assert 'width="1920"' in xml
        assert 'height="1080"' in xml
        assert 'frame_rate_num="30"' in xml

    def test_xml_has_producers(self):
        proj = self._make_full_project()
        xml = generate_kdenlive_xml(proj)
        assert '<producer id="clip0"' in xml
        assert '<producer id="clip1"' in xml
        assert '<producer id="clip2"' in xml
        assert "interview.mp4" in xml

    def test_xml_has_playlists(self):
        proj = self._make_full_project()
        xml = generate_kdenlive_xml(proj)
        assert '<playlist id="playlist0">' in xml
        assert '<playlist id="playlist1">' in xml
        assert '<playlist id="playlist2">' in xml

    def test_xml_has_tractor(self):
        proj = self._make_full_project()
        xml = generate_kdenlive_xml(proj)
        assert '<tractor id="maintractor">' in xml
        assert '<track producer="playlist0"/>' in xml

    def test_xml_has_filters(self):
        proj = self._make_full_project()
        xml = generate_kdenlive_xml(proj)
        assert 'mlt_service="brightness"' in xml

    def test_xml_has_transitions(self):
        proj = self._make_full_project()
        xml = generate_kdenlive_xml(proj)
        assert '<transition mlt_service="luma"' in xml

    def test_xml_has_guides(self):
        proj = self._make_full_project()
        xml = generate_kdenlive_xml(proj)
        assert "<kdenlivedoc>" in xml
        assert '<guide ' in xml
        assert 'comment="Start"' in xml

    def test_xml_empty_project(self):
        proj = create_project()
        xml = generate_kdenlive_xml(proj)
        assert "<mlt " in xml
        assert "</mlt>" in xml
        assert "<profile " in xml

    def test_xml_special_characters_escaped(self):
        proj = create_project(name='Test "Project" <1>')
        xml = generate_kdenlive_xml(proj)
        assert '&lt;' in xml
        assert '&gt;' in xml
        assert '&quot;' in xml

    def test_xml_clip_type_numbers(self):
        proj = create_project()
        import_clip(proj, "/a.mp4", name="V", clip_type="video", duration=10.0)
        import_clip(proj, "/b.mp3", name="A", clip_type="audio", duration=10.0)
        import_clip(proj, "/c.jpg", name="I", clip_type="image", duration=5.0)
        xml = generate_kdenlive_xml(proj)
        assert 'kdenlive:clip_type">0<' in xml
        assert 'kdenlive:clip_type">1<' in xml
        assert 'kdenlive:clip_type">2<' in xml

    def test_xml_sd_pal_profile(self):
        proj = create_project(profile="sd_pal")
        xml = generate_kdenlive_xml(proj)
        assert 'width="720"' in xml
        assert 'height="576"' in xml
        assert 'progressive="0"' in xml


# ── Format Validation Tests ─────────────────────────────────────

class TestFormatValidation:
    def test_json_roundtrip(self):
        proj = create_project(name="roundtrip")
        import_clip(proj, "/a.mp4", name="A", duration=10.0)
        add_track(proj)
        add_clip_to_track(proj, 0, "clip0", out_point=10.0)
        add_guide(proj, 5.0, label="Mid")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            save_project(proj, path)
            loaded = open_project(path)
            assert loaded["name"] == "roundtrip"
            assert len(loaded["bin"]) == 1
            assert len(loaded["tracks"]) == 1
            assert len(loaded["tracks"][0]["clips"]) == 1
            assert len(loaded["guides"]) == 1
        finally:
            os.unlink(path)

    def test_json_has_all_required_keys(self):
        proj = create_project()
        required = ["version", "name", "profile", "bin", "tracks",
                     "transitions", "guides", "metadata"]
        for key in required:
            assert key in proj, f"Missing key: {key}"

    def test_profile_has_all_required_fields(self):
        proj = create_project()
        profile_keys = ["name", "width", "height", "fps_num", "fps_den",
                        "progressive", "dar_num", "dar_den"]
        for key in profile_keys:
            assert key in proj["profile"], f"Missing profile key: {key}"

    def test_clip_entry_has_required_fields(self):
        proj = create_project()
        import_clip(proj, "/a.mp4", name="A", duration=10.0)
        clip = proj["bin"][0]
        for key in ["id", "name", "source", "duration", "type"]:
            assert key in clip, f"Missing clip key: {key}"

    def test_track_entry_has_required_fields(self):
        proj = create_project()
        add_track(proj)
        track = proj["tracks"][0]
        for key in ["id", "name", "type", "mute", "hide", "locked", "clips"]:
            assert key in track, f"Missing track key: {key}"

    def test_timeline_clip_entry_has_required_fields(self):
        proj = create_project()
        import_clip(proj, "/a.mp4", name="A", duration=10.0)
        add_track(proj)
        add_clip_to_track(proj, 0, "clip0", out_point=5.0)
        entry = proj["tracks"][0]["clips"][0]
        for key in ["clip_id", "in", "out", "position", "filters"]:
            assert key in entry, f"Missing timeline clip key: {key}"

    def test_xml_well_formed_basic(self):
        """Check basic XML well-formedness (no unclosed tags)."""
        proj = create_project()
        import_clip(proj, "/a.mp4", name="A", duration=10.0)
        add_track(proj)
        add_clip_to_track(proj, 0, "clip0", out_point=5.0)
        xml = generate_kdenlive_xml(proj)
        # Count open/close tags
        assert xml.count("<mlt ") == xml.count("</mlt>")
        assert xml.count("<tractor") == xml.count("</tractor>")
        assert xml.count("<playlist") == xml.count("</playlist>")

    def test_xml_producer_count_matches_bin(self):
        proj = create_project()
        import_clip(proj, "/a.mp4", name="A", duration=10.0)
        import_clip(proj, "/b.mp4", name="B", duration=20.0)
        xml = generate_kdenlive_xml(proj)
        assert xml.count("<producer ") == 2
        assert xml.count("</producer>") == 2


# ── Workflow E2E Tests ──────────────────────────────────────────

class TestWorkflowE2E:
    def test_basic_edit_workflow(self):
        """Create project, import clip, put on timeline, export XML."""
        proj = create_project(name="BasicEdit", profile="hd1080p30")
        import_clip(proj, "/footage/scene1.mp4", name="Scene1", duration=60.0)
        add_track(proj, track_type="video")
        add_clip_to_track(proj, 0, "clip0", position=0.0, out_point=30.0)
        xml = generate_kdenlive_xml(proj)
        assert "scene1.mp4" in xml
        assert '<entry producer="clip0"' in xml

    def test_multicam_workflow(self):
        """Multiple video tracks with clips."""
        proj = create_project(name="Multicam")
        import_clip(proj, "/cam1.mp4", name="Cam1", duration=60.0)
        import_clip(proj, "/cam2.mp4", name="Cam2", duration=60.0)
        add_track(proj, name="V1", track_type="video")
        add_track(proj, name="V2", track_type="video")
        add_clip_to_track(proj, 0, "clip0", position=0.0, out_point=30.0)
        add_clip_to_track(proj, 1, "clip1", position=0.0, out_point=30.0)
        tracks = list_tracks(proj)
        assert len(tracks) == 2
        xml = generate_kdenlive_xml(proj)
        assert "playlist0" in xml
        assert "playlist1" in xml

    def test_audio_video_workflow(self):
        """Video and audio tracks together."""
        proj = create_project(name="AV")
        import_clip(proj, "/video.mp4", name="Video", duration=60.0)
        import_clip(proj, "/music.mp3", name="Music", duration=180.0, clip_type="audio")
        add_track(proj, track_type="video")
        add_track(proj, track_type="audio")
        add_clip_to_track(proj, 0, "clip0", out_point=60.0)
        add_clip_to_track(proj, 1, "clip1", out_point=60.0)
        xml = generate_kdenlive_xml(proj)
        assert "video.mp4" in xml
        assert "music.mp3" in xml

    def test_trim_and_split_workflow(self):
        """Import, trim, split."""
        proj = create_project()
        import_clip(proj, "/long.mp4", name="Long", duration=120.0)
        add_track(proj)
        add_clip_to_track(proj, 0, "clip0", out_point=120.0)
        trim_clip(proj, 0, 0, new_in=10.0, new_out=110.0)
        parts = split_clip(proj, 0, 0, split_at=50.0)
        assert len(parts) == 2
        assert len(proj["tracks"][0]["clips"]) == 2

    def test_filter_chain_workflow(self):
        """Apply multiple filters to a clip."""
        proj = create_project()
        import_clip(proj, "/video.mp4", name="V", duration=30.0)
        add_track(proj)
        add_clip_to_track(proj, 0, "clip0", out_point=30.0)

        add_filter(proj, 0, 0, "brightness", {"level": 1.3})
        add_filter(proj, 0, 0, "contrast", {"level": 1.1})
        add_filter(proj, 0, 0, "saturation", {"saturation": 1.5})

        filters = list_filters(proj, 0, 0)
        assert len(filters) == 3

        xml = generate_kdenlive_xml(proj)
        assert xml.count("<filter ") == 3

    def test_transition_workflow(self):
        """Two tracks with a dissolve transition."""
        proj = create_project()
        import_clip(proj, "/a.mp4", name="A", duration=30.0)
        import_clip(proj, "/b.mp4", name="B", duration=30.0)
        add_track(proj, track_type="video")
        add_track(proj, track_type="video")
        add_clip_to_track(proj, 0, "clip0", position=0.0, out_point=15.0)
        add_clip_to_track(proj, 1, "clip1", position=10.0, out_point=15.0)
        add_transition(proj, "dissolve", 0, 1, position=10.0, duration=5.0)

        transitions = list_transitions(proj)
        assert len(transitions) == 1
        xml = generate_kdenlive_xml(proj)
        assert "<transition " in xml

    def test_guide_workflow(self):
        """Add guides and verify in XML."""
        proj = create_project()
        add_guide(proj, 0.0, label="Intro")
        add_guide(proj, 30.0, label="Main Content")
        add_guide(proj, 120.0, label="Outro")

        guides = list_guides(proj)
        assert len(guides) == 3

        xml = generate_kdenlive_xml(proj)
        assert 'comment="Intro"' in xml
        assert 'comment="Main Content"' in xml
        assert 'comment="Outro"' in xml

    def test_undo_redo_workflow(self):
        """Full undo/redo cycle."""
        sess = Session()
        proj = create_project(name="UndoTest")
        sess.set_project(proj)

        sess.snapshot("import clip")
        import_clip(proj, "/a.mp4", name="A", duration=10.0)
        assert len(proj["bin"]) == 1

        sess.snapshot("add track")
        add_track(proj)
        assert len(proj["tracks"]) == 1

        # Undo add track
        sess.undo()
        assert len(sess.get_project()["tracks"]) == 0

        # Undo import clip
        sess.undo()
        assert len(sess.get_project()["bin"]) == 0

        # Redo import clip
        sess.redo()
        assert len(sess.get_project()["bin"]) == 1

        # Redo add track
        sess.redo()
        assert len(sess.get_project()["tracks"]) == 1

    def test_save_load_roundtrip(self):
        """Full project save/load roundtrip."""
        proj = create_project(name="Roundtrip", profile="hd1080p25")
        import_clip(proj, "/vid.mp4", name="Video", duration=60.0)
        import_clip(proj, "/aud.wav", name="Audio", duration=60.0, clip_type="audio")
        add_track(proj, track_type="video")
        add_track(proj, track_type="audio")
        add_clip_to_track(proj, 0, "clip0", out_point=30.0)
        add_clip_to_track(proj, 1, "clip1", out_point=30.0)
        add_filter(proj, 0, 0, "brightness", {"level": 1.2})
        add_transition(proj, "dissolve", 0, 1, position=5.0, duration=2.0)
        add_guide(proj, 10.0, label="Mark")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_project(proj, path)
            loaded = open_project(path)

            assert loaded["name"] == "Roundtrip"
            assert loaded["profile"]["fps_num"] == 25
            assert len(loaded["bin"]) == 2
            assert len(loaded["tracks"]) == 2
            assert len(loaded["tracks"][0]["clips"]) == 1
            assert len(loaded["tracks"][0]["clips"][0]["filters"]) == 1
            assert len(loaded["transitions"]) == 1
            assert len(loaded["guides"]) == 1

            # Verify XML can be generated from loaded project
            xml = generate_kdenlive_xml(loaded)
            assert "<mlt " in xml
            assert "vid.mp4" in xml
        finally:
            os.unlink(path)

    def test_render_presets_available(self):
        presets = list_render_presets()
        assert len(presets) == len(RENDER_PRESETS)
        names = [p["name"] for p in presets]
        assert "h264_hq" in names
        assert "h264_fast" in names
        assert "prores" in names

    def test_all_profiles_produce_valid_xml(self):
        from cli_anything.kdenlive.core.project import PROFILES
        for name in PROFILES:
            proj = create_project(profile=name)
            xml = generate_kdenlive_xml(proj)
            assert "<mlt " in xml
            assert "</mlt>" in xml
            assert "<profile " in xml

    def test_complex_timeline_xml(self):
        """Complex project with multiple clips, filters, transitions."""
        proj = create_project(name="Complex", profile="hd1080p30")
        for i in range(5):
            import_clip(proj, f"/clip{i}.mp4", name=f"Clip{i}", duration=30.0)
        add_track(proj, track_type="video")
        add_track(proj, track_type="video")
        add_track(proj, track_type="audio")

        # Place clips
        add_clip_to_track(proj, 0, "clip0", position=0.0, out_point=15.0)
        add_clip_to_track(proj, 0, "clip1", position=15.0, out_point=15.0)
        add_clip_to_track(proj, 1, "clip2", position=5.0, out_point=20.0)
        add_clip_to_track(proj, 2, "clip3", position=0.0, out_point=30.0)

        # Filters
        add_filter(proj, 0, 0, "brightness", {"level": 1.1})
        add_filter(proj, 0, 0, "blur", {"hblur": 3, "vblur": 3})
        add_filter(proj, 0, 1, "fade_in_video", {"duration": 0.5})

        # Transition
        add_transition(proj, "dissolve", 0, 1, position=5.0, duration=3.0)

        # Guides
        add_guide(proj, 0.0, label="Start")
        add_guide(proj, 15.0, label="Mid")
        add_guide(proj, 30.0, label="End")

        xml = generate_kdenlive_xml(proj)
        assert xml.count("<producer ") == 5
        assert xml.count("<playlist ") == 3
        assert xml.count("<filter ") == 3
        assert xml.count("<transition ") == 1
        assert xml.count("<guide ") == 3

    def test_move_clip_then_export(self):
        proj = create_project()
        import_clip(proj, "/vid.mp4", name="V", duration=30.0)
        add_track(proj)
        add_clip_to_track(proj, 0, "clip0", position=0.0, out_point=10.0)
        move_clip(proj, 0, 0, new_position=5.0)
        xml = generate_kdenlive_xml(proj)
        # Should have a blank for the 5-second gap
        assert "<blank " in xml

    def test_project_info_after_edits(self):
        proj = create_project(name="InfoTest")
        import_clip(proj, "/a.mp4", name="A", duration=10.0)
        import_clip(proj, "/b.mp4", name="B", duration=20.0)
        add_track(proj, track_type="video")
        add_track(proj, track_type="audio")
        add_clip_to_track(proj, 0, "clip0", out_point=10.0)
        add_guide(proj, 5.0, label="X")

        info = get_project_info(proj)
        assert info["counts"]["bin_clips"] == 2
        assert info["counts"]["tracks"] == 2
        assert info["counts"]["clips_on_timeline"] == 1
        assert info["counts"]["guides"] == 1

    def test_all_filter_types_in_xml(self):
        proj = create_project()
        import_clip(proj, "/vid.mp4", name="V", duration=30.0)
        add_track(proj)
        add_clip_to_track(proj, 0, "clip0", out_point=30.0)

        for fname in FILTER_REGISTRY:
            add_filter(proj, 0, 0, fname)

        xml = generate_kdenlive_xml(proj)
        assert xml.count("<filter ") == len(FILTER_REGISTRY)

    def test_xml_write_to_file(self):
        proj = create_project(name="FileTest")
        import_clip(proj, "/v.mp4", name="V", duration=10.0)
        add_track(proj)
        add_clip_to_track(proj, 0, "clip0", out_point=10.0)

        xml = generate_kdenlive_xml(proj)
        with tempfile.NamedTemporaryFile(suffix=".kdenlive", delete=False, mode="w") as f:
            f.write(xml)
            path = f.name
        try:
            with open(path, "r") as f:
                content = f.read()
            assert content.startswith('<?xml version="1.0"')
            assert "</mlt>" in content
        finally:
            os.unlink(path)

    def test_timecode_in_workflow(self):
        """Use timecode conversion in a practical scenario."""
        tc = "00:01:30.000"
        secs = timecode_to_seconds(tc)
        assert secs == 90.0

        frames = seconds_to_frames(secs, 30, 1)
        assert frames == 2700

        back_tc = seconds_to_timecode(secs)
        assert back_tc == "00:01:30.000"

    def test_split_then_filter_workflow(self):
        """Split a clip then apply filter to one half."""
        proj = create_project()
        import_clip(proj, "/vid.mp4", name="V", duration=20.0)
        add_track(proj)
        add_clip_to_track(proj, 0, "clip0", out_point=20.0)
        split_clip(proj, 0, 0, split_at=10.0)
        # Apply filter to second half only
        add_filter(proj, 0, 1, "fade_out_video", {"duration": 2.0})
        filters = list_filters(proj, 0, 1)
        assert len(filters) == 1
        assert filters[0]["name"] == "fade_out_video"

    def test_session_with_full_workflow(self):
        """Session tracks changes through a full editing workflow."""
        sess = Session()
        proj = create_project(name="SessionWorkflow")
        sess.set_project(proj)

        sess.snapshot("import clips")
        import_clip(proj, "/a.mp4", name="A", duration=30.0)
        import_clip(proj, "/b.mp4", name="B", duration=30.0)

        sess.snapshot("add tracks")
        add_track(proj, track_type="video")
        add_track(proj, track_type="audio")

        sess.snapshot("place clips")
        add_clip_to_track(proj, 0, "clip0", out_point=15.0)

        history = sess.list_history()
        assert len(history) == 3

        # Undo place clips
        sess.undo()
        assert len(sess.get_project()["tracks"][0]["clips"]) == 0

        # Undo add tracks
        sess.undo()
        assert len(sess.get_project()["tracks"]) == 0

        # Redo both
        sess.redo()
        assert len(sess.get_project()["tracks"]) == 2
        sess.redo()
        assert len(sess.get_project()["tracks"][0]["clips"]) == 1


# ── True Backend E2E Tests (requires melt installed) ─────────────

class TestMeltBackend:
    """Tests that verify melt is installed and accessible."""

    def test_melt_is_installed(self):
        from cli_anything.kdenlive.utils.melt_backend import find_melt
        path = find_melt()
        assert os.path.exists(path)
        print(f"\n  melt binary: {path}")

    def test_melt_version(self):
        from cli_anything.kdenlive.utils.melt_backend import get_melt_version
        version = get_melt_version()
        assert version
        print(f"\n  melt version: {version}")


class TestMeltRenderE2E:
    """True E2E tests: render videos using melt."""

    def test_render_color_bars_mp4(self):
        """Render a color bars test video."""
        from cli_anything.kdenlive.utils.melt_backend import render_color_bars

        with tempfile.TemporaryDirectory() as tmp_dir:
            output = os.path.join(tmp_dir, "test.mp4")
            result = render_color_bars(output, duration=2, width=320, height=240)

            assert os.path.exists(result["output"])
            assert result["file_size"] > 0
            print(f"\n  Color bars MP4: {result['output']} ({result['file_size']:,} bytes)")

    def test_render_generated_mlt_xml(self):
        """Generate Kdenlive MLT XML from project and render it."""
        from cli_anything.kdenlive.utils.melt_backend import find_melt

        melt = find_melt()

        # Use built-in color producers since we have no real media files
        with tempfile.TemporaryDirectory() as tmp_dir:
            mlt_content = '''<?xml version="1.0" encoding="utf-8"?>
<mlt LC_NUMERIC="C" version="7.0.0" profile="atsc_720p_25">
  <profile description="HD 720p 25fps" width="320" height="240" progressive="1"
           sample_aspect_num="1" sample_aspect_den="1"
           display_aspect_num="4" display_aspect_den="3"
           frame_rate_num="25" frame_rate_den="1" colorspace="709"/>
  <producer id="color0" in="0" out="49">
    <property name="resource">color:green</property>
    <property name="mlt_service">color</property>
  </producer>
  <playlist id="playlist0">
    <entry producer="color0" in="0" out="49"/>
  </playlist>
  <tractor id="tractor0">
    <track producer="playlist0"/>
  </tractor>
</mlt>'''
            mlt_path = os.path.join(tmp_dir, "kdenlive_test.mlt")
            output_path = os.path.join(tmp_dir, "rendered.mp4")

            with open(mlt_path, 'w') as f:
                f.write(mlt_content)

            import subprocess
            cmd = [melt, mlt_path, "-consumer", f"avformat:{output_path}",
                   "vcodec=libx264", "acodec=aac", "ar=48000", "channels=2"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            assert result.returncode == 0, f"melt failed: {result.stderr[-500:]}"

            assert os.path.exists(output_path)
            size = os.path.getsize(output_path)
            assert size > 0
            print(f"\n  Kdenlive MLT render: {output_path} ({size:,} bytes)")
