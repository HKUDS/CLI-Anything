"""Tests for the Shotcut CLI core modules."""

import os
import sys
import json
import xml.etree.ElementTree as ET
import tempfile
from pathlib import Path
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli_anything.shotcut.core import session as session_mod
from cli_anything.shotcut.core.session import Session
from cli_anything.shotcut.core import project as proj_mod
from cli_anything.shotcut.core import timeline as tl_mod
from cli_anything.shotcut.core import filters as filt_mod
from cli_anything.shotcut.core import media as media_mod
from cli_anything.shotcut.core import export as export_mod
from cli_anything.shotcut.core import transitions as trans_mod
from cli_anything.shotcut.core import compositing as comp_mod
from cli_anything.shotcut.core import preview as preview_mod
from cli_anything.shotcut.utils.time import (
    timecode_to_frames, frames_to_timecode, parse_time_input,
    frames_to_seconds, seconds_to_frames,
)
from cli_anything.shotcut.utils.mlt_xml import (
    create_blank_project, mlt_to_string, parse_mlt, write_mlt,
    get_property, set_property, get_main_tractor, get_tractor_tracks,
    get_all_producers, get_playlist_entries, find_element_by_id,
)

from .conftest import PROFILE_HD1080


# ============================================================================
# Timecode utilities
# ============================================================================

class TestTimecode:
    def test_plain_frame_number(self):
        assert timecode_to_frames("100") == 100

    def test_hh_mm_ss_mmm(self):
        frames = timecode_to_frames("00:00:01.000")
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
                f"Roundtrip failed: {original_frames} -> {tc} -> {back}"

    def test_invalid_timecode(self):
        with pytest.raises(ValueError):
            timecode_to_frames("invalid")

    def test_negative_frames(self):
        assert frames_to_timecode(-5) == "00:00:00.000"

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
        root = create_blank_project(PROFILE_HD1080)
        assert root.tag == "mlt"
        assert "Shotcut" in (root.get("title") or "")
        prof = root.find("profile")
        assert prof is not None
        assert prof.get("width") == "1920"
        assert get_main_tractor(root) is not None

    def test_main_tractor_structure(self):
        root = create_blank_project(PROFILE_HD1080)
        tractor = get_main_tractor(root)
        assert tractor.find("multitrack") is None
        tracks = tractor.findall("track")
        assert len(tracks) == 1
        assert tracks[0].get("producer") == "background"
        assert "Shotcut" in tractor.get("title")

    def test_write_and_parse(self, tmp_path):
        root = create_blank_project(PROFILE_HD1080)
        tmpfile = str(tmp_path / "test.mlt")
        write_mlt(root, tmpfile)
        parsed = parse_mlt(tmpfile)
        assert parsed.tag == "mlt"
        assert parsed.find("profile").get("width") == "1920"

    def test_write_mlt_normalizes_late_media_nodes(self, tmp_path):
        root = create_blank_project(PROFILE_HD1080)
        late_chain = ET.Element("chain")
        late_chain.set("id", "late_chain")
        late_chain.set("in", "00:00:00.000")
        late_chain.set("out", "00:00:01.000")
        set_property(late_chain, "resource", "/tmp/fake.mp4")
        set_property(late_chain, "mlt_service", "avformat-novalidate")
        root.append(late_chain)

        tmpfile = str(tmp_path / "ordered.mlt")
        write_mlt(root, tmpfile)
        parsed = parse_mlt(tmpfile)
        children = list(parsed)
        first_playlist_or_tractor = min(
            idx for idx, child in enumerate(children) if child.tag in ("playlist", "tractor")
        )
        late_idx = next(
            idx
            for idx, child in enumerate(children)
            if child.tag == "chain" and child.get("id") == "late_chain"
        )
        assert late_idx < first_playlist_or_tractor

    def test_properties(self):
        import xml.etree.ElementTree as ET
        elem = ET.Element("producer")
        set_property(elem, "resource", "/test/video.mp4")
        assert get_property(elem, "resource") == "/test/video.mp4"
        assert get_property(elem, "nonexistent") is None
        assert get_property(elem, "nonexistent", "default") == "default"

    def test_mlt_to_string(self):
        root = create_blank_project(PROFILE_HD1080)
        xml_str = mlt_to_string(root)
        assert "<?xml" in xml_str
        assert "<mlt" in xml_str


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

    def test_save_and_open(self, tmp_path):
        s = Session()
        s.new_project()
        path = str(tmp_path / "test.mlt")
        s.save_project(path)
        assert not s.is_modified
        s2 = Session()
        s2.open_project(path)
        assert s2.is_open
        assert s2.project_path == path

    def test_undo_redo(self):
        s = Session()
        s.new_project()
        assert not s.undo()
        s.checkpoint()
        from cli_anything.shotcut.utils.mlt_xml import add_track_to_tractor
        add_track_to_tractor(s.root, s.get_main_tractor(), "video")
        assert s.is_modified
        tracks_before = len(get_tractor_tracks(s.get_main_tractor()))
        assert s.undo()
        assert len(get_tractor_tracks(s.get_main_tractor())) < tracks_before
        assert s.redo()
        assert len(get_tractor_tracks(s.get_main_tractor())) == tracks_before

    def test_open_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            Session().open_project("/nonexistent/path.mlt")

    def test_save_without_project(self):
        with pytest.raises(RuntimeError):
            Session().save_project("/tmp/test.mlt")

    def test_status(self):
        s = Session()
        assert s.status()["project_open"] is False
        s.new_project()
        status = s.status()
        assert status["project_open"] is True
        assert "profile" in status

    def test_resolve_refs_clips_on_open(self, tmp_path, dummy_file):
        s = Session()
        s.new_project()
        tl_mod.add_track(s, "video")
        clip_id = media_mod.import_media(s, dummy_file)["clip_id"]
        tl_mod.add_clip(s, clip_id, 1, "00:00:00.000", "00:00:05.000")
        path = str(tmp_path / "resolve.mlt")
        s.save_project(path)

        s2 = Session()
        s2.open_project(path)
        assert len(media_mod.list_media(s2)) == 1
        assert "clip0" in s2._bin_chains
        assert s2._clip_id_counter == 1

    def test_import_undo_import_redo_no_conflict(self, session_with_track, dummy_file, tmp_path):
        s = session_with_track
        r1 = media_mod.import_media(s, dummy_file)
        clip_id_a = r1["clip_id"]
        tl_mod.add_clip(s, clip_id_a, 1, "00:00:00.000", "00:00:05.000")

        f2 = str(tmp_path / "b.mp4")
        Path(f2).write_bytes(b"dummy2")
        r2 = media_mod.import_media(s, f2)
        clip_id_b = r2["clip_id"]
        assert clip_id_a != clip_id_b
        assert len(media_mod.list_media(s)) == 2

        s.undo()  # undo import B
        assert len(media_mod.list_media(s)) == 1
        assert clip_id_a in s._bin_chains
        assert clip_id_b not in s._bin_chains

        f3 = str(tmp_path / "c.mp4")
        Path(f3).write_bytes(b"dummy3")
        r3 = media_mod.import_media(s, f3)
        clip_id_c = r3["clip_id"]
        assert clip_id_c in s._bin_chains
        assert len(media_mod.list_media(s)) == 2

        # redo stack cleared by new import, undo all the way back
        assert s.undo()  # undo import C
        assert s.undo()  # undo add_clip A
        assert s.undo()  # undo import A
        assert len(media_mod.list_media(s)) == 0

        # redo path: import A → add_clip A → import C (B is lost)
        s.redo()
        assert clip_id_a in s._bin_chains
        s.redo()
        s.redo()
        assert clip_id_c in s._bin_chains
        assert len(media_mod.list_media(s)) == 2

    def test_resolve_refs_tracks_on_open(self, tmp_path):
        s = Session()
        s.new_project()
        tl_mod.add_track(s, "video", "V1")
        tl_mod.add_track(s, "audio", "A1")
        path = str(tmp_path / "tracks.mlt")
        s.save_project(path)

        s2 = Session()
        s2.open_project(path)
        assert len(tl_mod.list_tracks(s2)) == 3

    def test_save_session_state(self, tmp_path, monkeypatch):
        monkeypatch.setattr(session_mod, "SESSION_DIR", tmp_path)
        s = Session("test_save_state")
        s.new_project()
        path = s.save_session_state()
        assert os.path.exists(path)
        state = json.load(open(path))
        assert state["session_id"] == "test_save_state"
        assert state["project_path"] is None

    def test_load_session_state(self, tmp_path, monkeypatch):
        monkeypatch.setattr(session_mod, "SESSION_DIR", tmp_path)
        s = Session("test_load")
        s.new_project()
        s.save_session_state()
        state = Session.load_session_state("test_load")
        assert state is not None
        assert state["session_id"] == "test_load"

    def test_load_session_state_nonexistent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(session_mod, "SESSION_DIR", tmp_path)
        assert Session.load_session_state("nonexistent") is None

    def test_list_sessions(self, tmp_path, monkeypatch):
        monkeypatch.setattr(session_mod, "SESSION_DIR", tmp_path)
        s1 = Session("list_s1")
        s1.new_project()
        s1.save_session_state()
        s2 = Session("list_s2")
        s2.new_project()
        s2.save_session_state()
        sessions = Session.list_sessions()
        assert len(sessions) >= 2
        ids = {s["session_id"] for s in sessions}
        assert "list_s1" in ids
        assert "list_s2" in ids

    def test_get_profile(self):
        s = Session()
        s.new_project()
        prof = s.get_profile()
        assert prof["width"] == "1920"
        assert prof["height"] == "1080"

    def test_get_profile_no_project(self):
        with pytest.raises(RuntimeError):
            Session().get_profile()

    def test_save_no_path(self):
        s = Session()
        s.new_project()
        with pytest.raises(RuntimeError, match="No save path"):
            s.save_project()

    def test_get_profile_no_profile_element(self, tmp_path):
        s = Session()
        root = ET.Element("mlt")
        s.root = root
        s._resolve_refs()
        prof = s.get_profile()
        assert prof == {}

    def test_snapshot_no_project(self):
        s = Session()
        assert s._snapshot() == b""

    def test_max_undo_depth(self):
        s = Session()
        s.new_project()
        for _ in range(55):
            s.checkpoint()
        assert len(s._undo_stack) <= session_mod.MAX_UNDO_DEPTH

    def test_list_sessions_handles_corrupt(self, tmp_path, monkeypatch):
        monkeypatch.setattr(session_mod, "SESSION_DIR", tmp_path)
        corrupt = tmp_path / "bad.json"
        corrupt.write_text("not valid json{{{")
        sessions = Session.list_sessions()
        assert isinstance(sessions, list)

    def test_undo_restores_clip_state(self, session_with_track, dummy_file):
        media_mod.import_media(session_with_track, dummy_file)
        assert len(session_with_track._bin_chains) == 1
        session_with_track.undo()
        assert len(session_with_track._bin_chains) == 0


class TestPreview:
    @staticmethod
    def _fake_bundle(tmp_path, bundle_id):
        bundle_dir = tmp_path / bundle_id
        artifacts_dir = bundle_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        hero_path = artifacts_dir / "hero.png"
        clip_path = artifacts_dir / "preview.mp4"
        hero_path.write_bytes(b"\x89PNG\r\n\x1a\npreview")
        clip_path.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        summary_path = bundle_dir / "summary.json"
        summary_path.write_text(json.dumps({"headline": "Shotcut quick preview", "facts": {"duration_s": 5.0}}))
        manifest_path = bundle_dir / "manifest.json"
        manifest_path.write_text(json.dumps({"bundle_id": bundle_id, "status": "ok"}))
        return {
            "bundle_id": bundle_id,
            "status": "ok",
            "_bundle_dir": str(bundle_dir),
            "_manifest_path": str(manifest_path),
            "_summary_path": str(summary_path),
            "cached": False,
        }

    def test_list_recipes(self):
        recipes = preview_mod.list_recipes()
        assert recipes
        assert recipes[0]["name"] == "quick"

    def test_capture_bundle(self, tmp_path, monkeypatch):
        session = Session("preview_test")
        session.new_project()

        def fake_render(session_obj, output_path, preset, width, height, overwrite, prefer_ffmpeg=False):
            Path(output_path).write_bytes(b"\x00\x00\x00\x18ftypmp42")
            return {
                "output": output_path,
                "method": "ffmpeg-filtergraph" if prefer_ffmpeg else "melt",
                "size_bytes": 12,
            }

        def fake_probe(path):
            return {
                "duration_seconds": 6.0,
                "video_streams": [{"width": 640, "height": 360}],
            }

        def fake_thumb(filepath, output_path, timecode, width, height):
            Path(output_path).write_bytes(b"\x89PNG\r\n\x1a\npreview")
            return {"output": output_path, "time": timecode}

        monkeypatch.setattr(export_mod, "render", fake_render)
        monkeypatch.setattr(media_mod, "probe_media", fake_probe)
        monkeypatch.setattr(media_mod, "generate_thumbnail", fake_thumb)

        manifest = preview_mod.capture(session, root_dir=str(tmp_path))
        assert manifest["software"] == "shotcut"
        assert manifest["recipe"] == "quick"
        assert manifest["status"] == "ok"
        assert manifest["cached"] is False
        assert any(item["role"] == "preview-clip" for item in manifest["artifacts"])
        assert any(item["role"] == "hero" for item in manifest["artifacts"])
        assert os.path.isfile(manifest["_manifest_path"])

    def test_latest_bundle(self, tmp_path, monkeypatch):
        session = Session("preview_test")
        session.new_project()

        def fake_render(session_obj, output_path, preset, width, height, overwrite, prefer_ffmpeg=False):
            Path(output_path).write_bytes(b"\x00\x00\x00\x18ftypmp42")
            return {"output": output_path, "method": "ffmpeg-filtergraph" if prefer_ffmpeg else "melt"}

        def fake_probe(path):
            return {
                "duration_seconds": 3.0,
                "video_streams": [{"width": 640, "height": 360}],
            }

        def fake_thumb(filepath, output_path, timecode, width, height):
            Path(output_path).write_bytes(b"\x89PNG\r\n\x1a\nthumb")
            return {"output": output_path, "time": timecode}

        monkeypatch.setattr(export_mod, "render", fake_render)
        monkeypatch.setattr(media_mod, "probe_media", fake_probe)
        monkeypatch.setattr(media_mod, "generate_thumbnail", fake_thumb)

        created = preview_mod.capture(session, root_dir=str(tmp_path))
        latest = preview_mod.latest(root_dir=str(tmp_path))
        assert latest["bundle_id"] == created["bundle_id"]

    def test_live_start_publishes_session(self, tmp_path, monkeypatch):
        session = Session("preview_live")
        session.new_project()
        project_path = tmp_path / "live-demo.mlt"
        session.save_project(str(project_path))
        bundle_manifest = self._fake_bundle(tmp_path / "bundles", "bundle-a")

        def fake_capture(*args, **kwargs):
            return dict(bundle_manifest)

        monkeypatch.setattr(preview_mod, "capture", fake_capture)

        live = preview_mod.live_start(
            session,
            root_dir=str(tmp_path),
            refresh_hint_ms=900,
            live_mode="poll",
            source_poll_ms=420,
        )
        assert live["protocol_version"] == preview_mod.LIVE_PROTOCOL_VERSION
        assert live["current_bundle_id"] == "bundle-a"
        assert live["refresh_hint_ms"] == 900
        assert live["live_mode"] == "poll"
        assert live["source_poll_ms"] == 420
        assert live["source_state"]["project_path"] == str(project_path)
        assert live["source_state"]["last_rendered_fingerprint"].startswith("sha256:")
        assert Path(live["_session_path"]).is_file()
        assert Path(live["_trajectory_path"]).is_file()
        assert (Path(live["_session_dir"]) / "current" / "manifest.json").is_file()
        trajectory = json.loads(Path(live["_trajectory_path"]).read_text(encoding="utf-8"))
        assert trajectory["step_count"] == 1
        assert trajectory["steps"][0]["bundle_id"] == "bundle-a"
        assert live["trajectory_step_count"] == 1

    def test_live_push_updates_history(self, tmp_path, monkeypatch):
        session = Session("preview_live")
        session.new_project()
        project_path = tmp_path / "live-demo.mlt"
        session.save_project(str(project_path))
        bundle_a = self._fake_bundle(tmp_path / "bundles", "bundle-a")
        bundle_b = self._fake_bundle(tmp_path / "bundles", "bundle-b")
        manifests = [dict(bundle_a), dict(bundle_b)]

        def fake_capture(*args, **kwargs):
            return manifests.pop(0)

        monkeypatch.setattr(preview_mod, "capture", fake_capture)

        started = preview_mod.live_start(session, root_dir=str(tmp_path))
        pushed = preview_mod.live_push(session, root_dir=str(tmp_path))
        assert started["current_bundle_id"] == "bundle-a"
        assert pushed["current_bundle_id"] == "bundle-b"
        assert pushed["history"][0]["bundle_id"] == "bundle-b"
        assert pushed["history"][1]["bundle_id"] == "bundle-a"
        trajectory = json.loads(Path(pushed["_trajectory_path"]).read_text(encoding="utf-8"))
        assert trajectory["step_count"] == 2
        assert [step["bundle_id"] for step in trajectory["steps"]] == ["bundle-a", "bundle-b"]
        assert pushed["current_step_id"] == "step-0002"

    def test_live_status_includes_trajectory_summary(self, tmp_path, monkeypatch):
        session = Session("preview_live")
        session.new_project()
        project_path = tmp_path / "live-demo.mlt"
        session.save_project(str(project_path))
        bundle_manifest = self._fake_bundle(tmp_path / "bundles", "bundle-a")

        monkeypatch.setattr(preview_mod, "capture", lambda *args, **kwargs: dict(bundle_manifest))

        preview_mod.live_start(session, root_dir=str(tmp_path), live_mode="manual")
        status = preview_mod.live_status(session, root_dir=str(tmp_path))
        summary = status["trajectory_summary"]
        assert summary["step_count"] == 1
        assert summary["latest_bundle_id"] == "bundle-a"
        assert summary["latest_publish_reason"] == "live-start"
        assert summary["recent_steps"][0]["step_id"] == "step-0001"

    def test_live_push_records_publish_time_when_bundle_is_reused(self, tmp_path, monkeypatch):
        session = Session("preview_live")
        session.new_project()
        project_path = tmp_path / "live-demo.mlt"
        session.save_project(str(project_path))
        bundle_manifest = self._fake_bundle(tmp_path / "bundles", "bundle-a")
        bundle_manifest["created_at"] = "2025-01-01T00:00:00Z"
        publish_times = [
            "2026-04-23T10:00:00Z",
            "2026-04-23T10:05:00Z",
        ]

        monkeypatch.setattr(preview_mod, "capture", lambda *args, **kwargs: dict(bundle_manifest))
        monkeypatch.setattr(preview_mod, "_now_iso", lambda: publish_times.pop(0))

        preview_mod.live_start(session, root_dir=str(tmp_path), live_mode="manual")
        pushed = preview_mod.live_push(session, root_dir=str(tmp_path))
        trajectory = json.loads(Path(pushed["_trajectory_path"]).read_text(encoding="utf-8"))

        assert len(pushed["history"]) == 1
        assert [step["bundle_id"] for step in trajectory["steps"]] == ["bundle-a", "bundle-a"]
        assert [step["command_finished_at"] for step in trajectory["steps"]] == [
            "2026-04-23T10:00:00Z",
            "2026-04-23T10:05:00Z",
        ]
        assert all(step["created_at"] == "2025-01-01T00:00:00Z" for step in trajectory["steps"])

    def test_live_stop_marks_session_stopped(self, tmp_path, monkeypatch):
        session = Session("preview_live")
        session.new_project()
        project_path = tmp_path / "live-demo.mlt"
        session.save_project(str(project_path))
        bundle_manifest = self._fake_bundle(tmp_path / "bundles", "bundle-a")

        def fake_capture(*args, **kwargs):
            return dict(bundle_manifest)

        monkeypatch.setattr(preview_mod, "capture", fake_capture)

        preview_mod.live_start(session, root_dir=str(tmp_path))
        stopped = preview_mod.live_stop(session, root_dir=str(tmp_path))
        assert stopped["status"] == "stopped"
        assert "stopped_at" in stopped

    def test_live_session_name_is_stable_for_same_project_path(self, tmp_path):
        project_path = tmp_path / "stable-demo.mlt"

        session_a = Session("session-a")
        session_a.new_project()
        session_a.save_project(str(project_path))

        session_b = Session("session-b")
        session_b.open_project(str(project_path))

        name_a = preview_mod._live_session_name(session_a, "quick")
        name_b = preview_mod._live_session_name(session_b, "quick")
        assert name_a == name_b

    def test_project_fingerprint_is_stable_across_sessions_for_saved_project(self, tmp_path):
        project_path = tmp_path / "stable-project.mlt"

        session_a = Session("session-a")
        session_a.new_project()
        session_a.save_project(str(project_path))

        session_b = Session("session-b")
        session_b.open_project(str(project_path))

        assert preview_mod._project_fingerprint(session_a) == preview_mod._project_fingerprint(session_b)

    def test_poll_live_session_once_captures_after_source_change(self, tmp_path, monkeypatch):
        session = Session("preview_live")
        session.new_project()
        project_path = tmp_path / "poll-demo.mlt"
        session.save_project(str(project_path))
        bundle_a = self._fake_bundle(tmp_path / "bundles", "bundle-a")
        bundle_b = self._fake_bundle(tmp_path / "bundles", "bundle-b")
        manifests = [dict(bundle_a), dict(bundle_b)]
        calls = []

        def fake_capture(*args, **kwargs):
            calls.append(kwargs.get("command"))
            return manifests.pop(0)

        monkeypatch.setattr(preview_mod, "capture", fake_capture)

        started = preview_mod.live_start(
            session,
            root_dir=str(tmp_path),
            live_mode="poll",
            source_poll_ms=preview_mod.MIN_SOURCE_POLL_MS,
        )
        started_session_dir = Path(started["_session_dir"])
        session_payload = json.loads(Path(started["_session_path"]).read_text())
        session_payload["source_state"]["last_rendered_fingerprint"] = "sha256:stale"
        Path(started["_session_path"]).write_text(json.dumps(session_payload, indent=2))

        result = preview_mod.poll_live_session_once(str(started_session_dir))
        refreshed = json.loads(Path(started["_session_path"]).read_text())
        trajectory = json.loads(Path(started["_session_dir"]).joinpath("trajectory.json").read_text())
        assert result["action"] == "captured"
        assert refreshed["current_bundle_id"] == "bundle-b"
        assert refreshed["source_state"]["last_rendered_fingerprint"].startswith("sha256:")
        assert refreshed["poller"]["last_capture_status"] == "ok"
        assert calls
        assert trajectory["step_count"] == 2
        assert trajectory["steps"][-1]["publish_reason"] == "auto-poll"

    def test_poll_live_session_once_exits_for_manual_mode(self, tmp_path, monkeypatch):
        session = Session("preview_live")
        session.new_project()
        project_path = tmp_path / "manual-demo.mlt"
        session.save_project(str(project_path))
        bundle_manifest = self._fake_bundle(tmp_path / "bundles", "bundle-a")

        def fake_capture(*args, **kwargs):
            return dict(bundle_manifest)

        monkeypatch.setattr(preview_mod, "capture", fake_capture)

        started = preview_mod.live_start(session, root_dir=str(tmp_path), live_mode="manual")
        result = preview_mod.poll_live_session_once(started["_session_dir"])
        refreshed = json.loads(Path(started["_session_path"]).read_text())
        assert result["action"] == "exit"
        assert refreshed["poller"]["running"] is False
        assert refreshed["poller"]["last_exit_reason"] == "live-mode:manual"


# ============================================================================
# Project module
# ============================================================================

class TestProject:
    def test_new_project(self):
        s = Session()
        result = proj_mod.new_project(s, "hd1080p30")
        assert result["profile"] == "hd1080p30"

    def test_new_project_invalid_profile(self):
        with pytest.raises(ValueError):
            proj_mod.new_project(Session(), "invalid_profile")

    def test_project_info(self, session):
        info = proj_mod.project_info(session)
        assert "profile" in info
        assert "tracks" in info
        assert "media_clips" in info

    def test_list_profiles(self):
        profiles = proj_mod.list_profiles()
        assert "hd1080p30" in profiles
        assert "4k30" in profiles

    def test_save_project(self, session, tmp_path):
        path = str(tmp_path / "test.mlt")
        result = proj_mod.save_project(session, path)
        assert result["path"] == path
        assert os.path.isfile(path)

    def test_open_and_info(self, session, tmp_path):
        path = str(tmp_path / "test.mlt")
        proj_mod.save_project(session, path)
        s2 = Session()
        result = proj_mod.open_project(s2, path)
        assert result["path"] == path

    def test_project_info_no_double_count_chains(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:05.000")
        info = proj_mod.project_info(session_with_track)
        assert len(info["media_clips"]) == 1

    def test_project_info_clip_count_excludes_transitions(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:10.000")
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:10.000")
        trans_mod.add_transition(session_with_track, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=14)
        info = proj_mod.project_info(session_with_track)
        assert info["tracks"][1]["clip_count"] == 2


# ============================================================================
# Timeline module
# ============================================================================

class TestTimeline:
    def test_list_tracks_initial(self, session):
        assert len(tl_mod.list_tracks(session)) >= 1

    def test_add_video_track(self, session):
        initial = len(tl_mod.list_tracks(session))
        result = tl_mod.add_track(session, "video", "V1")
        assert result["type"] == "video"
        assert len(tl_mod.list_tracks(session)) == initial + 1

    def test_add_audio_track(self, session):
        initial = len(tl_mod.list_tracks(session))
        result = tl_mod.add_track(session, "audio", "A1")
        assert result["type"] == "audio"
        assert len(tl_mod.list_tracks(session)) == initial + 1

    def test_add_invalid_track_type(self, session):
        with pytest.raises(ValueError):
            tl_mod.add_track(session, "invalid")

    def test_remove_track(self, session):
        tl_mod.add_track(session, "video", "V1")
        tl_mod.add_track(session, "video", "V2")
        count = len(tl_mod.list_tracks(session))
        tl_mod.remove_track(session, count - 1)
        assert len(tl_mod.list_tracks(session)) == count - 1

    def test_remove_track_middle(self, session):
        tl_mod.add_track(session, "video", "V1")
        tl_mod.add_track(session, "video", "V2")
        tl_mod.add_track(session, "audio", "A1")
        count = len(tl_mod.list_tracks(session))
        tl_mod.remove_track(session, 2)
        assert len(tl_mod.list_tracks(session)) == count - 1

    def test_remove_background_track_fails(self, session):
        with pytest.raises(IndexError):
            tl_mod.remove_track(session, 0)

    def test_add_clip_not_imported(self, session_with_track):
        with pytest.raises(ValueError, match="not imported"):
            tl_mod.add_clip(session_with_track, "clip999", 1)

    def test_add_and_list_clip(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1,
                        in_point="00:00:00.000", out_point="00:00:05.000")
        clips = tl_mod.list_clips(session_with_track, 1)
        assert len([c for c in clips if c.get("clip_index") is not None]) == 1

    def test_remove_clip(self, session_with_clip):
        tl_mod.remove_clip(session_with_clip, 1, 0)
        clips = [c for c in tl_mod.list_clips(session_with_clip, 1)
                 if c.get("clip_index") is not None]
        assert len(clips) == 0

    def test_remove_clip_without_ripple_preserves_inclusive_duration(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1,
                        in_point="00:00:00.000", out_point="00:00:01.000")
        tl_mod.remove_clip(session_with_track, 1, 0, ripple=False)
        blank = next(item for item in tl_mod.list_clips(session_with_track, 1)
                     if item.get("type") == "blank")
        assert parse_time_input(blank["length"]) == timecode_to_frames("00:00:01.000") + 1

    def test_trim_clip(self, session_with_clip):
        result = tl_mod.trim_clip(session_with_clip, 1, 0,
                                  in_point="00:00:02.000", out_point="00:00:04.000")
        assert result["new_in"] == "00:00:02.000"
        assert result["new_out"] == "00:00:04.000"

    def test_split_clip(self, session_with_clip):
        result = tl_mod.split_clip(session_with_clip, 1, 0, "00:00:03.000")
        expected_first_out = frames_to_timecode(timecode_to_frames("00:00:03.000") - 1)
        assert result["first_clip"]["out"] == expected_first_out
        assert result["second_clip"]["in"] == "00:00:03.000"
        clips = [c for c in tl_mod.list_clips(session_with_clip, 1)
                 if c.get("clip_index") is not None]
        assert len(clips) == 2

    def test_move_clip(self, session, dummy_file):
        tl_mod.add_track(session, "video", "V1")
        tl_mod.add_track(session, "video", "V2")
        clip_id = media_mod.import_media(session, dummy_file)["clip_id"]
        tl_mod.add_clip(session, clip_id, 1, "00:00:00.000", "00:00:05.000")
        tl_mod.move_clip(session, 1, 0, 2)
        assert len([c for c in tl_mod.list_clips(session, 1)
                    if c.get("clip_index") is not None]) == 0
        assert len([c for c in tl_mod.list_clips(session, 2)
                    if c.get("clip_index") is not None]) == 1

    def test_set_track_name(self, session_with_track):
        result = tl_mod.set_track_name(session_with_track, 1, "My Track")
        assert result["name"] == "My Track"

    def test_mute_unmute(self, session):
        tl_mod.add_track(session, "audio")
        idx = len(tl_mod.list_tracks(session)) - 1
        assert tl_mod.set_track_mute(session, idx, True)["mute"] is True
        assert tl_mod.set_track_mute(session, idx, False)["mute"] is False

    def test_show_timeline(self, session_with_track):
        result = tl_mod.show_timeline(session_with_track)
        assert "tracks" in result
        assert "fps_num" in result

    def test_add_blank(self, session_with_track):
        assert tl_mod.add_blank(session_with_track, 1, "00:00:02.000")["action"] == "add_blank"

    def test_add_clip_at_absolute_time(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        result = tl_mod.add_clip(
            session_with_track, clip_id, 1,
            in_point="00:00:00.000", out_point="00:00:02.000",
            at_time="00:00:05.000",
        )
        assert result["at_time"] == "00:00:05.000"
        clips = tl_mod.list_clips(session_with_track, 1)
        assert clips[0]["type"] == "blank"
        assert abs(
            parse_time_input(clips[0]["length"]) - parse_time_input("00:00:05.000")
        ) <= 1
        assert clips[1]["clip_index"] == 0

    def test_add_clip_at_absolute_time_rejects_overlap(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(
            session_with_track, clip_id, 1,
            in_point="00:00:00.000", out_point="00:00:05.000",
        )
        with pytest.raises(RuntimeError, match="overlaps an existing clip"):
            tl_mod.add_clip(
                session_with_track, clip_id, 1,
                in_point="00:00:00.000", out_point="00:00:02.000",
                at_time="00:00:03.000",
            )

    def test_add_clip_at_time_uses_inclusive_duration(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1,
                        in_point="00:00:00.000", out_point="00:00:01.000")
        next_start = frames_to_timecode(timecode_to_frames("00:00:01.000") + 1)
        tl_mod.add_clip(session_with_track, clip_id, 1,
                        in_point="00:00:00.000", out_point="00:00:01.000",
                        at_time=next_start)
        items = tl_mod.list_clips(session_with_track, 1)
        assert len([item for item in items if item.get("type") == "blank"]) == 0
        assert len([item for item in items if item.get("clip_index") is not None]) == 2

    def test_add_clip_at_time_inserts_gap(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        result = tl_mod.add_clip(
            session_with_track, clip_id, 1,
            in_point="00:00:00.000", out_point="00:00:02.000",
            at_time="00:00:08.000",
        )
        assert result["at_time"] == "00:00:08.000"
        clips = tl_mod.list_clips(session_with_track, 1)
        assert clips[0]["type"] == "blank"
        assert clips[1]["clip_index"] == 0

    def test_add_clip_at_time_rejects_overlap_after_clip(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(
            session_with_track, clip_id, 1,
            in_point="00:00:00.000", out_point="00:00:05.000",
        )
        with pytest.raises(RuntimeError, match="overlaps an existing clip"):
            tl_mod.add_clip(
                session_with_track, clip_id, 1,
                in_point="00:00:00.000", out_point="00:00:01.000",
                at_time="00:00:02.000",
            )

    def test_add_clip_at_boundary_between_clips(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        next_start = frames_to_timecode(timecode_to_frames("00:00:01.000") + 1)
        third_start = frames_to_timecode((timecode_to_frames("00:00:01.000") + 1) * 2)
        tl_mod.add_clip(session_with_track, clip_id, 1,
                        in_point="00:00:00.000", out_point="00:00:01.000")
        tl_mod.add_clip(session_with_track, clip_id, 1,
                        in_point="00:00:00.000", out_point="00:00:01.000",
                        at_time=next_start)
        tl_mod.add_clip(session_with_track, clip_id, 1,
                        in_point="00:00:00.000", out_point="00:00:01.000",
                        at_time=third_start)
        clips = tl_mod.list_clips(session_with_track, 1)
        real = [c for c in clips if c.get("clip_index") is not None]
        assert len(real) == 3
        playlist = session_with_track._track_playlists[1]
        children = list(playlist)
        entry_producers = [c.get("producer") for c in children if c.tag == "entry"]
        assert entry_producers == ["tl_clip0", "tl_clip0", "tl_clip0"]

    def test_add_clip_at_after_two_clips(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        next_start = frames_to_timecode(timecode_to_frames("00:00:01.000") + 1)
        third_start = frames_to_timecode((timecode_to_frames("00:00:01.000") + 1) * 2)
        tl_mod.add_clip(session_with_track, clip_id, 1,
                        in_point="00:00:00.000", out_point="00:00:01.000")
        tl_mod.add_clip(session_with_track, clip_id, 1,
                        in_point="00:00:00.000", out_point="00:00:01.000",
                        at_time=next_start)
        tl_mod.add_clip(session_with_track, clip_id, 1,
                        in_point="00:00:00.000", out_point="00:00:01.000",
                        at_time=third_start)
        clips = tl_mod.list_clips(session_with_track, 1)
        real = [c for c in clips if c.get("clip_index") is not None]
        assert len(real) == 3

    def test_undo_add_track(self, session):
        initial = len(tl_mod.list_tracks(session))
        tl_mod.add_track(session, "video")
        assert len(tl_mod.list_tracks(session)) == initial + 1
        session.undo()
        assert len(tl_mod.list_tracks(session)) == initial

    # --- Track index fixup after removal ---

    def test_remove_track_updates_tractor_out(self, session, dummy_file):
        tl_mod.add_track(session, "video")
        tl_mod.add_track(session, "video")
        clip_id = media_mod.import_media(session, dummy_file)["clip_id"]
        tl_mod.add_clip(session, clip_id, 1, "00:00:00.000", "00:00:10.000")
        tl_mod.add_clip(session, clip_id, 2, "00:00:00.000", "00:00:30.000")
        tl_mod.remove_track(session, 2)
        tractor = session.get_main_tractor()
        out = parse_time_input(tractor.get("out", "0"), 30000, 1001)
        expected = parse_time_input("00:00:10.000", 30000, 1001)
        assert out <= expected + 1

    def test_remove_middle_track_decrements_higher_transition_indices(self, session):
        tl_mod.add_track(session, "video", "V1")
        tl_mod.add_track(session, "video", "V2")
        tl_mod.add_track(session, "video", "V3")
        tl_mod.remove_track(session, 2)
        remaining = get_tractor_tracks(session.get_main_tractor())
        max_idx = len(remaining) - 1
        for trans in session.get_main_tractor().findall("transition"):
            a = int(get_property(trans, "a_track", "0") or "0")
            b = int(get_property(trans, "b_track", "0") or "0")
            assert a <= max_idx
            assert b <= max_idx

    def test_remove_middle_track_no_self_referencing_qtblend(self, session):
        tl_mod.add_track(session, "video", "V1")
        tl_mod.add_track(session, "video", "V2")
        tl_mod.add_track(session, "video", "V3")
        tl_mod.remove_track(session, 2)
        for trans in session.get_main_tractor().findall("transition"):
            if get_property(trans, "mlt_service", "") == "qtblend":
                a = int(get_property(trans, "a_track", "0") or "0")
                b = int(get_property(trans, "b_track", "0") or "0")
                assert a != b

    # --- Clip operations near transitions ---

    def test_add_clip_without_ffprobe_no_hardcoded_duration(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        result = tl_mod.add_clip(session_with_track, clip_id, 1, in_point="00:00:00.000")
        chain = find_element_by_id(session_with_track.root, result["chain_id"])
        assert chain is not None
        assert chain.get("out", "") != "00:00:10.000"

    def test_empty_timeline_resets_tractor_out(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:10.000")
        assert session_with_track.get_main_tractor().get("out") != "00:00:00.000"
        tl_mod.remove_clip(session_with_track, 1, 0)
        assert session_with_track.get_main_tractor().get("out", "00:00:00.000") == "00:00:00.000"

    def test_add_clip_position_skips_transitions(self, session_with_three_clips, dummy_file, tmp_path):
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=14)
        f2 = str(tmp_path / "second.mp4")
        Path(f2).write_bytes(b"dummy")
        clip_id2 = media_mod.import_media(session_with_three_clips, f2)["clip_id"]
        tl_mod.add_clip(session_with_three_clips, clip_id2, 1, position=3,
                        in_point="00:00:00.000", out_point="00:00:05.000")
        playlist = tl_mod._get_track_playlist(session_with_three_clips, 1)
        real = [e for e in get_playlist_entries(playlist)
                if e["type"] == "entry"
                and not tl_mod.is_transition_entry_by_dict(e, session_with_three_clips.root)]
        assert len(real) == 4
        assert len(trans_mod.list_transitions(session_with_three_clips)) == 1

    def test_remove_clip_non_ripple_after_transition(self, session_with_three_clips):
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=14)
        tl_mod.remove_clip(session_with_three_clips, 1, 2, ripple=False)
        playlist = tl_mod._get_track_playlist(session_with_three_clips, 1)
        entries = get_playlist_entries(playlist)
        blanks = [e for e in entries if e["type"] == "blank"]
        assert len(blanks) == 1
        real = [e for e in entries if e["type"] == "entry"
                and not tl_mod.is_transition_entry_by_dict(e, session_with_three_clips.root)]
        assert len(real) == 2

    def test_insert_before_transitioned_clip_removes_old_transition(self, session_with_three_clips, tmp_path):
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=14)
        f2 = str(tmp_path / "new.mp4")
        Path(f2).write_bytes(b"dummy")
        clip_id2 = media_mod.import_media(session_with_three_clips, f2)["clip_id"]
        tl_mod.add_clip(session_with_three_clips, clip_id2, 1, position=1,
                        in_point="00:00:00.000", out_point="00:00:05.000")
        playlist = tl_mod._get_track_playlist(session_with_three_clips, 1)
        trans_entries = [c for c in playlist
                         if c.tag == "entry" and tl_mod.is_transition_entry(c, session_with_three_clips.root)]
        assert len(trans_entries) == 0

    def test_move_clip_before_transition_removes_old_transition(self, session, dummy_file, tmp_path):
        f2 = str(tmp_path / "b.mp4")
        Path(f2).write_bytes(b"dummy")
        tl_mod.add_track(session, "video", "V1")
        tl_mod.add_track(session, "video", "V2")
        clip_id = media_mod.import_media(session, dummy_file)["clip_id"]
        tl_mod.add_clip(session, clip_id, 1, "00:00:00.000", "00:00:10.000")
        tl_mod.add_clip(session, clip_id, 1, "00:00:00.000", "00:00:10.000")
        trans_mod.add_transition(session, "dissolve", track_index=1, clip_a_index=0, duration_frames=14)
        clip_id2 = media_mod.import_media(session, f2)["clip_id"]
        tl_mod.add_clip(session, clip_id2, 2, "00:00:00.000", "00:00:10.000")
        tl_mod.move_clip(session, 2, 0, 1, 1)
        playlist = tl_mod._get_track_playlist(session, 1)
        trans_entries = [c for c in playlist
                         if c.tag == "entry" and tl_mod.is_transition_entry(c, session.root)]
        assert len(trans_entries) == 0

    def test_move_clip_uses_restored_in_out(self, session_with_three_clips):
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=14)
        tl_mod.add_track(session_with_three_clips, "video", "V2")
        orig_out = parse_time_input("00:00:10.000", 30000, 1001)
        tl_mod.move_clip(session_with_three_clips, 1, 0, 2)
        clips = tl_mod.list_clips(session_with_three_clips, 2)
        assert len(clips) == 1
        assert abs(parse_time_input(clips[0]["out"], 30000, 1001) - orig_out) <= 1

    def test_split_clip_with_transition_uses_correct_out(self, session_with_three_clips):
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=14)
        orig_out = parse_time_input("00:00:10.000", 30000, 1001)
        result = tl_mod.split_clip(session_with_three_clips, 1, 0, "00:00:05.000")
        expected_first_out = frames_to_timecode(timecode_to_frames("00:00:05.000") - 1)
        assert result["first_clip"]["out"] == expected_first_out
        assert abs(parse_time_input(result["second_clip"]["out"], 30000, 1001) - orig_out) <= 1


# ============================================================================
# Filters module
# ============================================================================

class TestFilters:
    def test_filter_catalog_completeness(self):
        result = filt_mod.list_available_filters()
        assert len(result) >= 50
        names = [f["name"] for f in result]
        categories = set(f["category"] for f in result)
        assert "audio" in categories
        assert "sharpen" in names or "brightness" in names
        color_filters = [n for n in names if n in
                         ("color-grading", "levels", "white-balance",
                          "contrast", "gamma", "vibrance", "invert",
                          "grayscale", "threshold", "posterize")]
        assert len(color_filters) >= 3

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

    def test_filter_info_has_params(self):
        info = filt_mod.get_filter_info("sharpen")
        assert "params" in info
        assert info["name"] == "sharpen"

    @pytest.mark.parametrize("filter_name", ["sharpen", "vignette", "grayscale", "invert"])
    def test_add_various_filters(self, filter_name, session_with_clip):
        result = filt_mod.add_filter(session_with_clip, filter_name,
                                     track_index=1, clip_index=0)
        assert result["action"] == "add_filter"
        assert result["filter_name"] == filter_name

    def test_add_filter_to_clip(self, session_with_clip):
        filt_mod.add_filter(session_with_clip, "brightness", track_index=1,
                           clip_index=0, params={"level": "1.5"})
        filters = filt_mod.list_filters(session_with_clip, track_index=1, clip_index=0)
        assert len(filters) == 1
        assert filters[0]["service"] == "brightness"

    def test_add_filter_to_track(self, session_with_clip):
        result = filt_mod.add_filter(session_with_clip, "volume", track_index=1)
        assert result["target"] == "track 1"
        assert len(filt_mod.list_filters(session_with_clip, track_index=1)) >= 1

    def test_add_global_filter(self, session):
        assert filt_mod.add_filter(session, "brightness")["target"] == "global"

    def test_remove_filter(self, session_with_clip):
        filt_mod.add_filter(session_with_clip, "brightness", track_index=1, clip_index=0)
        filt_mod.remove_filter(session_with_clip, 0, track_index=1, clip_index=0)
        assert len(filt_mod.list_filters(session_with_clip, track_index=1, clip_index=0)) == 0

    def test_set_filter_param(self, session_with_clip):
        filt_mod.add_filter(session_with_clip, "brightness", track_index=1, clip_index=0)
        result = filt_mod.set_filter_param(session_with_clip, 0, "level", "0.5",
                                           track_index=1, clip_index=0)
        assert result["new_value"] == "0.5"

    def test_undo_add_filter(self, session_with_clip):
        filt_mod.add_filter(session_with_clip, "brightness", track_index=1, clip_index=0)
        assert len(filt_mod.list_filters(session_with_clip, track_index=1, clip_index=0)) == 1
        session_with_clip.undo()
        assert len(filt_mod.list_filters(session_with_clip, track_index=1, clip_index=0)) == 0

    def test_set_volume_envelope(self, session_with_clip):
        result = filt_mod.set_volume_envelope(
            session_with_clip,
            [("00:00:00.000", "1.0"), ("00:00:03.000", "0.25"), ("00:00:04.000", "1.0")],
            track_index=1,
        )
        assert result["action"] == "set_volume_envelope"
        filters = filt_mod.list_filters(session_with_clip, track_index=1)
        assert filters[0]["service"] == "volume"
        assert filters[0]["params"]["level"].count("=") == 3

    def test_duck_volume(self, session_with_clip):
        result = filt_mod.duck_volume(
            session_with_clip,
            [("00:00:01.000", "00:00:02.000")],
            track_index=1,
            normal_level=1.0,
            duck_level=0.3,
        )
        assert result["action"] == "duck_volume"
        filters = filt_mod.list_filters(session_with_clip, track_index=1)
        assert "0.3" in filters[0]["params"]["level"]

    def test_duck_window_dotdot_split(self):
        windows_cli = ["00:00:01.000..00:00:03.000"]
        parsed = []
        for w in windows_cli:
            start_tc, end_tc = w.split("..", 1)
            parsed.append((start_tc, end_tc))
        assert parsed == [("00:00:01.000", "00:00:03.000")]


# ============================================================================
# Media module
# ============================================================================

class TestMedia:
    def test_probe_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            media_mod.probe_media("/nonexistent/file.mp4")

    def test_probe_basic(self, dummy_file):
        result = media_mod.probe_media(dummy_file)
        assert result["filename"] == os.path.basename(dummy_file)
        assert result["size_bytes"] > 0

    def test_probe_basic_video_type(self, dummy_file):
        result = media_mod.probe_media(dummy_file)
        assert result["media_type"] == "video"

    def test_probe_basic_audio_type(self, tmp_path):
        p = tmp_path / "audio.mp3"
        p.write_bytes(b"dummy")
        result = media_mod.probe_media(str(p))
        assert result["media_type"] == "audio"

    def test_probe_basic_image_type(self, tmp_path, monkeypatch):
        monkeypatch.setattr(media_mod, "_find_tool", lambda name: None)
        p = tmp_path / "image.png"
        p.write_bytes(b"dummy")
        result = media_mod.probe_media(str(p))
        assert result["media_type"] == "image"

    def test_parse_fps_fraction(self):
        assert media_mod._parse_fps("30000/1001") == 29.97

    def test_parse_fps_integer(self):
        assert media_mod._parse_fps("30") == 30.0

    def test_parse_fps_zero_denominator(self):
        assert media_mod._parse_fps("30/0") == 0.0

    def test_parse_fps_invalid(self):
        assert media_mod._parse_fps("abc") == 0.0

    def test_list_media_empty(self, session):
        assert media_mod.list_media(session) == []

    def test_list_media_with_clip(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:05.000")
        result = media_mod.list_media(session_with_track)
        assert len(result) >= 1
        assert any(dummy_file in m["resource"] for m in result)

    def test_list_media_no_double_count(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:05.000")
        assert len(media_mod.list_media(session_with_track)) == 1

    def test_import_media_returns_clip_id(self, session_with_track, dummy_file):
        result = media_mod.import_media(session_with_track, dummy_file)
        assert result["clip_id"] == "clip0"
        assert result["source"] == os.path.abspath(dummy_file)

    def test_import_media_idempotent(self, session_with_track, dummy_file):
        r1 = media_mod.import_media(session_with_track, dummy_file)
        r2 = media_mod.import_media(session_with_track, dummy_file)
        assert r1["clip_id"] == r2["clip_id"]
        assert r2["already_imported"] is True

    def test_import_media_no_project(self, dummy_file):
        s = Session()
        with pytest.raises(RuntimeError, match="No project"):
            media_mod.import_media(s, dummy_file)

    def test_import_media_file_not_found(self, session_with_track):
        with pytest.raises(FileNotFoundError):
            media_mod.import_media(session_with_track, "/nonexistent.mp4")

    def test_import_media_sets_modified(self, session, dummy_file):
        tl_mod.add_track(session, "video")
        assert session.is_modified is True
        session.undo()
        assert session.is_modified is False
        media_mod.import_media(session, dummy_file)
        assert session.is_modified is True

    def test_import_media_undo(self, session_with_track, dummy_file):
        media_mod.import_media(session_with_track, dummy_file)
        assert len(media_mod.list_media(session_with_track)) == 1
        session_with_track.undo()
        assert len(media_mod.list_media(session_with_track)) == 0

    def test_get_clip_info(self, session_with_track, dummy_file):
        result = media_mod.import_media(session_with_track, dummy_file)
        info = media_mod.get_clip_info(session_with_track, result["clip_id"])
        assert info["clip_id"] == "clip0"
        assert dummy_file in info["resource"]

    def test_get_clip_info_not_found(self, session_with_track):
        with pytest.raises(ValueError, match="not found"):
            media_mod.get_clip_info(session_with_track, "clip999")

    def test_check_media_files_present(self, session_with_track, dummy_file):
        media_mod.import_media(session_with_track, dummy_file)
        result = media_mod.check_media_files(session_with_track)
        assert result["total"] == 1
        assert result["all_present"] is True

    def test_check_media_files_empty(self, session):
        result = media_mod.check_media_files(session)
        assert result["total"] == 0
        assert result["all_present"] is True

    def test_check_media_files_missing(self, session_with_track, tmp_path):
        f = tmp_path / "temp_video.mp4"
        f.write_bytes(b"dummy")
        media_mod.import_media(session_with_track, str(f))
        os.unlink(str(f))
        result = media_mod.check_media_files(session_with_track)
        assert result["all_present"] is False
        assert len(result["missing"]) == 1

    def test_probe_basic_mlt_type(self, tmp_path, monkeypatch):
        monkeypatch.setattr(media_mod, "_find_tool", lambda name: None)
        p = tmp_path / "project.mlt"
        p.write_bytes(b"<mlt></mlt>")
        result = media_mod.probe_media(str(p))
        assert result["media_type"] == "mlt_project"

    def test_import_media_with_caption(self, session_with_track, dummy_file):
        result = media_mod.import_media(session_with_track, dummy_file, caption="My Clip")
        assert result["caption"] == "My Clip"


# ============================================================================
# Export module
# ============================================================================

class TestExport:
    def test_list_presets(self):
        result = export_mod.list_presets()
        names = [p["name"] for p in result]
        assert "default" in names
        assert "h264-high" in names

    def test_list_presets_contains_defaults(self):
        result = export_mod.list_presets()
        names = [p["name"] for p in result]
        assert "default" in names
        assert "h264-high" in names

    def test_get_preset_info(self):
        assert export_mod.get_preset_info("default")["vcodec"] == "libx264"

    def test_unknown_preset(self):
        with pytest.raises(ValueError):
            export_mod.get_preset_info("nonexistent")

    def test_render_no_project(self):
        with pytest.raises(RuntimeError):
            export_mod.render(Session(), "/tmp/output.mp4")

    def test_render_no_overwrite(self, session_with_track, dummy_file, tmp_path):
        out = str(tmp_path / "out.mp4")
        open(out, 'wb').write(b"existing")
        with pytest.raises(FileExistsError):
            export_mod.render(session_with_track, out)

    def test_export_updates_tractor_out_with_trailing_blank(self, session_with_track, dummy_file, tmp_path):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:05.000")
        tl_mod.add_blank(session_with_track, 1, "00:00:03.000")
        out = str(tmp_path / "out.mp4")
        try:
            export_mod.render(session_with_track, out, overwrite=True)
        except (FileNotFoundError, RuntimeError):
            pass
        expected = parse_time_input("00:00:08.000", 30000, 1001)
        actual = parse_time_input(session_with_track.get_main_tractor().get("out", "0"), 30000, 1001)
        assert abs(actual - expected) <= 1

    def test_set_tractor_out_single_clip(self, session_with_track, dummy_file):
        """_update_tractor_out sets tractor out to match a single clip duration."""
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:05.000")

        tractor = get_main_tractor(session_with_track.root)
        assert tractor.get("out") != "00:00:00.000"
        assert tractor.get("out") != "04:00:00.000"
        bg = find_element_by_id(session_with_track.root, "background")
        bg_entry = bg.find("entry")
        assert bg_entry.get("out") == tractor.get("out")

    def test_set_tractor_out_multi_segment(self, session_with_track, dummy_file):
        """_update_tractor_out sums entry spans and blanks across segments."""
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:03.000")
        tl_mod.add_blank(session_with_track, 1, "00:00:01.000")
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:03.000")

        tractor = get_main_tractor(session_with_track.root)
        out_tc = tractor.get("out")
        assert out_tc != "00:00:00.000"
        assert out_tc != "04:00:00.000"

    def test_set_tractor_out_empty_timeline(self):
        """_update_tractor_out is a no-op on a blank project with no clips."""
        s = Session()
        proj_mod.new_project(s, "hd1080p30")
        tractor = get_main_tractor(s.root)

        assert tractor.get("out") == "00:00:00.000"


# ============================================================================
# Integration
# ============================================================================

class TestIntegration:
    def test_full_workflow(self, dummy_file, tmp_path):
        s = Session()
        proj_mod.new_project(s, "hd1080p30")
        tl_mod.add_track(s, "video", "V1")
        tl_mod.add_track(s, "audio", "A1")
        clip_id = media_mod.import_media(s, dummy_file)["clip_id"]
        tl_mod.add_clip(s, clip_id, 1, "00:00:00.000", "00:00:05.000", caption="Intro")
        tl_mod.add_clip(s, clip_id, 1, "00:00:00.000", "00:00:10.000", caption="Main")
        filt_mod.add_filter(s, "brightness", track_index=1, clip_index=0, params={"level": "1.2"})
        tl_mod.trim_clip(s, 1, 1, in_point="00:00:02.000")
        path = str(tmp_path / "project.mlt")
        proj_mod.save_project(s, path)
        s2 = Session()
        proj_mod.open_project(s2, path)
        assert proj_mod.project_info(s2)["media_clips"][0]["resource"] == dummy_file
        tl_mod.add_track(s, "video", "V2")
        s.undo()

    def test_save_load_roundtrip_preserves_filters(self, dummy_file, tmp_path):
        s = Session()
        proj_mod.new_project(s)
        tl_mod.add_track(s, "video")
        clip_id = media_mod.import_media(s, dummy_file)["clip_id"]
        tl_mod.add_clip(s, clip_id, 1, "00:00:00.000", "00:00:05.000")
        filt_mod.add_filter(s, "brightness", track_index=1, clip_index=0, params={"level": "0.8"})
        path = str(tmp_path / "project.mlt")
        proj_mod.save_project(s, path)
        s2 = Session()
        proj_mod.open_project(s2, path)
        found = False
        for prod in get_all_producers(s2.root):
            for filt in prod.findall("filter"):
                if get_property(filt, "mlt_service") == "brightness":
                    assert get_property(filt, "level") == "0.8"
                    found = True
        assert found


# ============================================================================
# Timeline edge cases
# ============================================================================

class TestTimelineEdgeCases:
    def test_add_blank(self, session_with_clip):
        result = tl_mod.add_blank(session_with_clip, 1, "00:00:02.000")
        assert result["action"] == "add_blank"
        clips = tl_mod.list_clips(session_with_clip, 1)
        blanks = [c for c in clips if c.get("type") == "blank"]
        assert len(blanks) == 1

    def test_set_track_mute(self, session_with_track):
        result = tl_mod.set_track_mute(session_with_track, 1, True)
        assert result["action"] == "set_track_mute"
        tracks = tl_mod.list_tracks(session_with_track)
        audio_track = [t for t in tracks if t["index"] == 1][0]
        assert "audio" in audio_track.get("hide", "")

    def test_set_track_unmute(self, session_with_track):
        tl_mod.set_track_mute(session_with_track, 1, True)
        tl_mod.set_track_mute(session_with_track, 1, False)
        tracks = tl_mod.list_tracks(session_with_track)
        audio_track = [t for t in tracks if t["index"] == 1][0]
        assert "audio" not in audio_track.get("hide", "")

    def test_set_track_hidden(self, session_with_track):
        result = tl_mod.set_track_hidden(session_with_track, 1, True)
        assert result["action"] == "set_track_hidden"
        tracks = tl_mod.list_tracks(session_with_track)
        video_track = [t for t in tracks if t["index"] == 1][0]
        assert "video" in video_track.get("hide", "")

    def test_set_track_unhidden(self, session_with_track):
        tl_mod.set_track_hidden(session_with_track, 1, True)
        tl_mod.set_track_hidden(session_with_track, 1, False)
        tracks = tl_mod.list_tracks(session_with_track)
        video_track = [t for t in tracks if t["index"] == 1][0]
        assert "video" not in video_track.get("hide", "")

    def test_set_track_hidden_while_muted(self, session_with_track):
        tl_mod.set_track_mute(session_with_track, 1, True)
        tl_mod.set_track_hidden(session_with_track, 1, True)
        tracks = tl_mod.list_tracks(session_with_track)
        track = [t for t in tracks if t["index"] == 1][0]
        assert track["hide"] == "both"

    def test_unhide_while_both(self, session_with_track):
        tl_mod.set_track_mute(session_with_track, 1, True)
        tl_mod.set_track_hidden(session_with_track, 1, True)
        tl_mod.set_track_hidden(session_with_track, 1, False)
        tracks = tl_mod.list_tracks(session_with_track)
        track = [t for t in tracks if t["index"] == 1][0]
        assert track["hide"] == "audio"

    def test_remove_adjacent_transitions_both_sides(self, session_with_three_clips):
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=14)
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1,
                                 clip_a_index=1, duration_frames=14)
        tl_mod.remove_clip(session_with_three_clips, 1, 1)
        remaining = trans_mod.list_transitions(session_with_three_clips)
        assert len(remaining) == 0
        clips = tl_mod.list_clips(session_with_three_clips, 1)
        real = [c for c in clips if "clip_index" in c]
        assert len(real) == 2

    def test_remove_adjacent_transitions_preserves_distant(self, session_with_three_clips):
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=14)
        tl_mod.remove_clip(session_with_three_clips, 1, 2)
        remaining = trans_mod.list_transitions(session_with_three_clips)
        assert len(remaining) == 1

    def test_set_track_name(self, session_with_track):
        tl_mod.set_track_name(session_with_track, 1, "MyTrack")
        tracks = tl_mod.list_tracks(session_with_track)
        assert tracks[1]["name"] == "MyTrack"

    def test_remove_clip_no_ripple(self, session_with_two_clips):
        tl_mod.remove_clip(session_with_two_clips, 1, 0, ripple=False)
        clips = tl_mod.list_clips(session_with_two_clips, 1)
        blanks = [c for c in clips if c.get("type") == "blank"]
        real = [c for c in clips if "clip_index" in c]
        assert len(blanks) == 1
        assert len(real) == 1

    def test_move_clip(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:05.000")
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:05.000", "00:00:10.000")
        tl_mod.move_clip(session_with_track, 1, 0, to_track=1, to_position=1)
        clips = tl_mod.list_clips(session_with_track, 1)
        real = [c for c in clips if "clip_index" in c]
        assert len(real) == 2

    def test_list_tracks_invalid_index(self, session_with_track):
        with pytest.raises(IndexError):
            tl_mod.set_track_name(session_with_track, 99, "bad")

    def test_list_tracks_no_project(self):
        with pytest.raises(RuntimeError):
            tl_mod.list_tracks(Session())

    def test_show_timeline_no_project(self):
        with pytest.raises(RuntimeError):
            tl_mod.show_timeline(Session())

    def test_add_clip_no_project(self, dummy_file):
        with pytest.raises(ValueError, match="not imported"):
            tl_mod.add_clip(Session(), "clip0", 1, None, None)

    def test_add_clip_not_imported(self, session_with_track):
        with pytest.raises(ValueError, match="not imported"):
            tl_mod.add_clip(session_with_track, "clip999", 1, None, None)

    def test_remove_clip_out_of_range(self, session_with_clip):
        with pytest.raises(IndexError):
            tl_mod.remove_clip(session_with_clip, 1, 99)

    def test_get_track_playlist_invalid(self, session):
        with pytest.raises(IndexError, match="out of range"):
            tl_mod._get_track_playlist(session, 99)


# ============================================================================
# Transitions module
# ============================================================================

class TestTransitions:
    def test_list_available_transitions(self):
        names = [t["name"] for t in trans_mod.list_available_transitions()]
        assert len(names) >= 10
        assert "dissolve" in names
        assert "wipe-left" in names

    def test_list_by_category_video(self):
        names = [t["name"] for t in trans_mod.list_available_transitions("video")]
        assert "dissolve" in names
        assert "crossfade" not in names

    def test_list_by_category_audio(self):
        names = [t["name"] for t in trans_mod.list_available_transitions("audio")]
        assert "crossfade" in names

    def test_get_transition_info(self):
        info = trans_mod.get_transition_info("dissolve")
        assert info["service"] == "luma"
        assert "params" in info

    def test_get_transition_info_invalid(self):
        with pytest.raises(ValueError):
            trans_mod.get_transition_info("nonexistent_transition")

    def test_add_transition(self, session_with_two_clips):
        result = trans_mod.add_transition(session_with_two_clips, "dissolve",
                                          track_index=1, clip_a_index=0, duration_frames=14)
        assert result["service"] == "luma"

    def test_add_transition_with_params(self, session_with_two_clips):
        result = trans_mod.add_transition(session_with_two_clips, "dissolve",
                                          track_index=1, clip_a_index=0,
                                          duration_frames=14, params={"softness": "0.5"})
        assert result["params"]["softness"] == "0.5"

    def test_add_wipe_transition(self, session_with_two_clips):
        result = trans_mod.add_transition(session_with_two_clips, "wipe-left",
                                          track_index=1, clip_a_index=0)
        assert result["params"]["resource"] == "%luma01.pgm"

    def test_add_transition_invalid_track(self, session_with_two_clips):
        with pytest.raises(IndexError):
            trans_mod.add_transition(session_with_two_clips, "dissolve", track_index=99, clip_a_index=0)

    def test_add_raw_service_transition(self, session_with_two_clips):
        assert trans_mod.add_transition(
            session_with_two_clips, "luma", track_index=1, clip_a_index=0,
            duration_frames=14, params={"softness": "0.3"})["service"] == "luma"

    def test_list_transitions_empty(self, session):
        assert trans_mod.list_transitions(session) == []

    def test_list_transitions_after_add(self, session_with_two_clips):
        trans_mod.add_transition(session_with_two_clips, "dissolve", track_index=1, clip_a_index=0)
        result = trans_mod.list_transitions(session_with_two_clips)
        assert len(result) >= 1
        assert result[-1]["service"] == "luma"

    def test_remove_transition(self, session_with_two_clips):
        trans_mod.add_transition(session_with_two_clips, "dissolve", track_index=1, clip_a_index=0)
        baseline = len(trans_mod.list_transitions(session_with_two_clips))
        trans_mod.remove_transition(session_with_two_clips, 0)
        assert len(trans_mod.list_transitions(session_with_two_clips)) == baseline - 1

    def test_remove_transition_invalid_index(self, session):
        with pytest.raises(IndexError):
            trans_mod.remove_transition(session, 0)

    def test_set_transition_param(self, session_with_two_clips):
        trans_mod.add_transition(session_with_two_clips, "dissolve", track_index=1, clip_a_index=0)
        result = trans_mod.set_transition_param(session_with_two_clips, 0, "softness", "0.8")
        assert result["new_value"] == "0.8"

    def test_undo_add_transition(self, session_with_two_clips):
        baseline = len(trans_mod.list_transitions(session_with_two_clips))
        trans_mod.add_transition(session_with_two_clips, "dissolve", track_index=1, clip_a_index=0)
        session_with_two_clips.undo()
        assert len(trans_mod.list_transitions(session_with_two_clips)) == baseline

    def test_multiple_transitions(self, session_with_three_clips, dummy_file):
        clip_id = media_mod.import_media(session_with_three_clips, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_three_clips, clip_id,
                        1, "00:00:00.000", "00:00:10.000")
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1, clip_a_index=0)
        trans_mod.add_transition(session_with_three_clips, "wipe-left", track_index=1, clip_a_index=1)
        assert len(trans_mod.list_transitions(session_with_three_clips)) >= 2

    def test_transition_tractor_before_playlist(self, session_with_two_clips):
        trans_mod.add_transition(session_with_two_clips, "dissolve", track_index=1, clip_a_index=0)
        playlist = tl_mod._get_track_playlist(session_with_two_clips, 1)
        trans_tractors = [c for c in session_with_two_clips.root
                          if c.tag == "tractor" and c.get("id") != "tractor0"
                          and get_property(c, "shotcut:transition")]
        assert len(trans_tractors) == 1
        assert list(session_with_two_clips.root).index(trans_tractors[0]) < \
               list(session_with_two_clips.root).index(playlist)

    def test_transition_tractor_has_in_out(self, session_with_two_clips):
        trans_mod.add_transition(session_with_two_clips, "dissolve", track_index=1, clip_a_index=0)
        tt = [c for c in session_with_two_clips.root
              if c.tag == "tractor" and c.get("id") != "tractor0"
              and get_property(c, "shotcut:transition")][0]
        assert tt.get("in") == "00:00:00.000"
        assert tt.get("out") is not None

    def test_add_track_after_transition(self, session_with_two_clips):
        trans_mod.add_transition(session_with_two_clips, "dissolve", track_index=1, clip_a_index=0)
        tl_mod.add_track(session_with_two_clips, "video", "V2")
        assert len(get_tractor_tracks(session_with_two_clips.get_main_tractor())) == 3

    def test_list_transitions_has_track_producers(self, session_with_two_clips):
        trans_mod.add_transition(session_with_two_clips, "dissolve", track_index=1, clip_a_index=0)
        assert len(trans_mod.list_transitions(session_with_two_clips)[0]["track_producers"]) == 2

    def test_remove_transition_restores_clip_lengths(self, session_with_two_clips):
        fps_num, fps_den = 30000, 1001
        tractor = session_with_two_clips.get_main_tractor()
        pl = find_element_by_id(session_with_two_clips.root,
                                get_tractor_tracks(tractor)[1].get("producer"))
        entries = [c for c in pl if c.tag == "entry"]
        orig_a_out = parse_time_input(entries[0].get("out"), fps_num, fps_den)
        orig_b_in = parse_time_input(entries[1].get("in"), fps_num, fps_den)
        trans_mod.add_transition(session_with_two_clips, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=14)
        trans_mod.remove_transition(session_with_two_clips, 0)
        clip_entries = [c for c in pl if c.tag == "entry"]
        assert abs(parse_time_input(clip_entries[0].get("out"), fps_num, fps_den) - orig_a_out) <= 1
        assert abs(parse_time_input(clip_entries[1].get("in"), fps_num, fps_den) - orig_b_in) <= 1

    def test_add_transition_rejects_blank_gap(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:10.000")
        tl_mod.add_blank(session_with_track, 1, "00:00:02.000")
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:10.000")
        with pytest.raises(ValueError, match="blank gap"):
            trans_mod.add_transition(session_with_track, "dissolve", track_index=1, clip_a_index=0)

    # --- Edge cases from code review ---

    def test_audio_track_no_qtblend(self, session):
        tl_mod.add_track(session, "video")
        tl_mod.add_track(session, "audio")
        tractor = session.get_main_tractor()
        qtblend_audio = [t for t in tractor.findall("transition")
                         if get_property(t, "mlt_service") == "qtblend"
                         and get_property(t, "b_track") == "2"]
        assert len(qtblend_audio) == 0
        mix_audio = [t for t in tractor.findall("transition")
                     if get_property(t, "mlt_service") == "mix"
                     and get_property(t, "b_track") == "2"]
        assert len(mix_audio) == 1

    def test_remove_clip_cleans_adjacent_transitions(self, session_with_three_clips):
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1, clip_a_index=0)
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1, clip_a_index=1)
        assert len(trans_mod.list_transitions(session_with_three_clips)) == 2
        tl_mod.remove_clip(session_with_three_clips, 1, 1)
        assert len(trans_mod.list_transitions(session_with_three_clips)) == 0

    def test_trim_clip_updates_adjacent_transition(self, session_with_three_clips):
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1, clip_a_index=0)
        tl_mod.trim_clip(session_with_three_clips, 1, 0, out_point="00:00:05.000")
        trans_list = trans_mod.list_transitions(session_with_three_clips)
        if trans_list:
            trans_tractor = find_element_by_id(session_with_three_clips.root, trans_list[0]["id"])
            if trans_tractor is not None:
                track_a_out = parse_time_input(trans_tractor.findall("track")[0].get("out", "0"), 30000, 1001)
                clip_out = parse_time_input("00:00:05.000", 30000, 1001)
                assert track_a_out <= clip_out

    def test_remove_track_cleans_transition_tractors(self, session_with_three_clips, dummy_file, tmp_path):
        tl_mod.add_track(session_with_three_clips, "video", "V2")
        f2 = str(tmp_path / "v2.mp4")
        Path(f2).write_bytes(b"dummy")
        clip_id2 = media_mod.import_media(session_with_three_clips, f2)["clip_id"]
        tl_mod.add_clip(session_with_three_clips, clip_id2, 2, "00:00:00.000", "00:00:10.000")
        tl_mod.add_clip(session_with_three_clips, clip_id2, 2, "00:00:00.000", "00:00:10.000")
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=2, clip_a_index=0)
        tl_mod.remove_track(session_with_three_clips, 2)
        assert len(trans_mod.list_transitions(session_with_three_clips)) == 0
        orphaned = [c for c in session_with_three_clips.root
                    if c.tag == "tractor" and c.get("id") != "tractor0"
                    and get_property(c, "shotcut:transition")]
        assert len(orphaned) == 0

    def test_trim_clip_retime_updates_all_transition_outs(self, session_with_three_clips):
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=14)
        tl_mod.trim_clip(session_with_three_clips, 1, 0, out_point="00:00:03.000")
        trans_list = trans_mod.list_transitions(session_with_three_clips)
        if trans_list:
            tt = find_element_by_id(session_with_three_clips.root, trans_list[0]["id"])
            if tt is not None:
                assert tt.get("out") == tt.findall("transition")[0].get("out")

    def test_trim_clip_in_point_shortens_transition(self, session_with_three_clips):
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=14)
        tl_mod.trim_clip(session_with_three_clips, 1, 1, in_point="00:00:09.990")
        for trans in trans_mod._get_user_transitions(session_with_three_clips.root):
            for t in trans.findall("track"):
                assert parse_time_input(t.get("in", "0"), 30000, 1001) <= \
                       parse_time_input(t.get("out", "0"), 30000, 1001)

    def test_crossfade_single_mix_transition(self, session_with_three_clips):
        trans_mod.add_transition(session_with_three_clips, "crossfade", track_index=1, clip_a_index=0)
        transitions = trans_mod._get_user_transitions(session_with_three_clips.root)
        mix_count = sum(1 for t in transitions[0].findall("transition")
                        if get_property(t, "mlt_service") == "mix")
        assert mix_count == 1

    def test_retime_gives_frames_back_to_other_clip(self, session_with_three_clips, tmp_path):
        f2 = str(tmp_path / "retime_test.mp4")
        Path(f2).write_bytes(b"dummy")
        clip_id2 = media_mod.import_media(session_with_three_clips, f2)["clip_id"]
        tl_mod.add_clip(session_with_three_clips, clip_id2, 1, "00:00:00.000", "00:00:10.000")
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1,
                                 clip_a_index=2, duration_frames=100)
        tractor = session_with_three_clips.get_main_tractor()
        pl = find_element_by_id(session_with_three_clips.root,
                                get_tractor_tracks(tractor)[1].get("producer"))
        entries_before = [c for c in pl if c.tag == "entry"
                         and not tl_mod.is_transition_entry(c, session_with_three_clips.root)]
        b_in_before = parse_time_input(entries_before[3].get("in"), 30000, 1001)
        tl_mod.trim_clip(session_with_three_clips, 1, 2, out_point="00:00:07.000")
        assert len(trans_mod.list_transitions(session_with_three_clips)) == 1
        entries_after = [c for c in pl if c.tag == "entry"
                        and not tl_mod.is_transition_entry(c, session_with_three_clips.root)]
        b_in_after = parse_time_input(entries_after[3].get("in"), 30000, 1001)
        assert b_in_after < b_in_before

    def test_add_transition_rejects_duplicate(self, session_with_three_clips):
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1, clip_a_index=0)
        with pytest.raises(ValueError, match="already exists"):
            trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1, clip_a_index=0)

    def test_short_clip_transition_no_invalid_range(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:00.200")
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:00.200")
        trans_mod.add_transition(session_with_track, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=14)
        for c in tl_mod.list_clips(session_with_track, 1):
            if "clip_index" in c:
                assert parse_time_input(c["out"], 30000, 1001) > parse_time_input(c["in"], 30000, 1001)

    def test_insert_then_remove_transition_restores_correct_clips(self, session_with_three_clips, tmp_path):
        fps_num, fps_den = 30000, 1001
        tractor = session_with_three_clips.get_main_tractor()
        pl = find_element_by_id(session_with_three_clips.root,
                                get_tractor_tracks(tractor)[1].get("producer"))
        entries = [c for c in pl if c.tag == "entry" and not tl_mod.is_transition_entry(c, session_with_three_clips.root)]
        orig_a_out = parse_time_input(entries[0].get("out"), fps_num, fps_den)
        orig_b_in = parse_time_input(entries[1].get("in"), fps_num, fps_den)
        trans_mod.add_transition(session_with_three_clips, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=14)
        f2 = str(tmp_path / "new.mp4")
        Path(f2).write_bytes(b"newclip")
        clip_id2 = media_mod.import_media(session_with_three_clips, f2)["clip_id"]
        tl_mod.add_clip(session_with_three_clips, clip_id2, 1, position=2,
                        in_point="00:00:00.000", out_point="00:00:03.000")
        trans_mod.remove_transition(session_with_three_clips, 0)
        entries_after = [c for c in pl if c.tag == "entry" and not tl_mod.is_transition_entry(c, session_with_three_clips.root)]
        assert abs(parse_time_input(entries_after[0].get("out"), fps_num, fps_den) - orig_a_out) <= 1
        assert abs(parse_time_input(entries_after[1].get("in"), fps_num, fps_den) - orig_b_in) <= 1

    def test_remove_transition_odd_frames_no_loss(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:10.000")
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:10.000")
        fps_num, fps_den = 30000, 1001
        trans_frames = 15
        trans_mod.add_transition(session_with_track, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=trans_frames)
        pl = tl_mod._get_track_playlist(session_with_track, 1)
        entries = [c for c in pl if c.tag == "entry" and not tl_mod.is_transition_entry(c, session_with_track.root)]
        trimmed_a_out = parse_time_input(entries[0].get("out"), fps_num, fps_den)
        trimmed_b_in = parse_time_input(entries[1].get("in"), fps_num, fps_den)
        trans_mod.remove_transition(session_with_track, 0)
        clip_entries = [c for c in pl if c.tag == "entry" and not tl_mod.is_transition_entry(c, session_with_track.root)]
        restored_a_out = parse_time_input(clip_entries[0].get("out"), fps_num, fps_den)
        restored_b_in = parse_time_input(clip_entries[1].get("in"), fps_num, fps_den)
        total_restored = (restored_a_out - trimmed_a_out) + (trimmed_b_in - restored_b_in)
        assert total_restored == trans_frames

    def test_trim_clip_b_reanchors_track_a_in_transition(self, session_with_track, dummy_file, tmp_path):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        f2 = str(tmp_path / "b_reanchor.mp4")
        Path(f2).write_bytes(b"dummy")
        clip_id2 = media_mod.import_media(session_with_track, f2)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:10.000")
        tl_mod.add_clip(session_with_track, clip_id2, 1, "00:00:00.000", "00:00:10.000")
        trans_mod.add_transition(session_with_track, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=14)
        trans_entries = [c for c in list(session_with_track.root)
                         if c.tag == "tractor" and get_property(c, "shotcut:transition") is not None]
        old_a_in = trans_entries[0].findall("track")[0].get("in")
        tl_mod.trim_clip(session_with_track, 1, 1, in_point="00:00:00.200")
        new_a_in = trans_entries[0].findall("track")[0].get("in")
        assert new_a_in != old_a_in

    def test_remove_transition_after_retime_uses_track_bounds(self, session_with_track, dummy_file, tmp_path):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        f2 = str(tmp_path / "retime_bounds.mp4")
        Path(f2).write_bytes(b"dummy")
        clip_id2 = media_mod.import_media(session_with_track, f2)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:10.000")
        tl_mod.add_clip(session_with_track, clip_id2, 1, "00:00:05.000", "00:00:15.000")
        trans_mod.add_transition(session_with_track, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=14)
        tl_mod.trim_clip(session_with_track, 1, 0, out_point="00:00:09.700")
        clips = [c for c in tl_mod.list_clips(session_with_track, 1) if "clip_index" in c]
        entry_a_out = clips[0]["out"]
        entry_b_in = clips[1]["in"]
        fps_num, fps_den = 30000, 1001
        trans_mod.remove_transition(session_with_track, 0)
        clips_after = [c for c in tl_mod.list_clips(session_with_track, 1) if "clip_index" in c]
        assert parse_time_input(clips_after[0]["out"], fps_num, fps_den) - \
               parse_time_input(entry_a_out, fps_num, fps_den) > 0
        assert parse_time_input(entry_b_in, fps_num, fps_den) - \
               parse_time_input(clips_after[1]["in"], fps_num, fps_den) > 0

    def test_list_transitions_shows_mix_params(self, session_with_track, dummy_file):
        clip_id = media_mod.import_media(session_with_track, dummy_file)["clip_id"]
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:10.000")
        tl_mod.add_clip(session_with_track, clip_id, 1, "00:00:00.000", "00:00:10.000")
        trans_mod.add_transition(session_with_track, "dissolve", track_index=1,
                                 clip_a_index=0, duration_frames=14)
        transitions = trans_mod.list_transitions(session_with_track)
        assert len(transitions) == 1
        assert "progressive" in transitions[0]["params"]


# ============================================================================
# Compositing module
# ============================================================================

class TestCompositing:
    def test_list_blend_modes(self):
        result = comp_mod.list_blend_modes()
        names = [m["name"] for m in result]
        assert len(result) >= 18
        assert "normal" in names
        assert "multiply" in names

    def test_set_track_blend_mode(self, session_with_two_tracks):
        result = comp_mod.set_track_blend_mode(session_with_two_tracks, 2, "multiply")
        assert result["blend_mode"] == "multiply"

    def test_set_blend_mode_invalid(self, session_with_two_tracks):
        with pytest.raises(ValueError):
            comp_mod.set_track_blend_mode(session_with_two_tracks, 2, "nonexistent_mode")

    def test_set_blend_mode_background_track(self, session_with_two_tracks):
        with pytest.raises(ValueError):
            comp_mod.set_track_blend_mode(session_with_two_tracks, 0, "multiply")

    def test_get_track_blend_mode_default(self, session_with_two_tracks):
        assert comp_mod.get_track_blend_mode(session_with_two_tracks, 2)["blend_mode"] == "normal"

    def test_get_track_blend_mode_after_set(self, session_with_two_tracks):
        comp_mod.set_track_blend_mode(session_with_two_tracks, 2, "screen")
        assert comp_mod.get_track_blend_mode(session_with_two_tracks, 2)["blend_mode"] == "screen"

    def test_set_track_opacity(self, session_with_two_tracks):
        result = comp_mod.set_track_opacity(session_with_two_tracks, 1, 0.5)
        assert result["opacity"] == 0.5

    def test_set_track_opacity_invalid_range(self, session_with_two_tracks):
        with pytest.raises(ValueError):
            comp_mod.set_track_opacity(session_with_two_tracks, 1, 1.5)
        with pytest.raises(ValueError):
            comp_mod.set_track_opacity(session_with_two_tracks, 1, -0.1)

    def test_set_track_opacity_invalid_index(self, session_with_two_tracks):
        with pytest.raises(IndexError):
            comp_mod.set_track_opacity(session_with_two_tracks, 99, 0.5)

    def test_set_track_opacity_update_existing(self, session_with_two_tracks):
        comp_mod.set_track_opacity(session_with_two_tracks, 1, 0.5)
        assert comp_mod.set_track_opacity(session_with_two_tracks, 1, 0.8)["opacity"] == 0.8

    def test_pip_position(self, session_with_two_tracks):
        result = comp_mod.pip_position(session_with_two_tracks, 2, 0,
                                       x="10%", y="10%", width="40%", height="40%", opacity=0.9)
        assert result["geometry"] == "10%/10%:40%x40%:90"

    def test_pip_position_defaults(self, session_with_two_tracks):
        result = comp_mod.pip_position(session_with_two_tracks, 2, 0)
        assert result["geometry"] == "0/0:100%x100%:100"

    def test_pip_position_invalid_track(self, session_with_two_tracks):
        with pytest.raises(IndexError):
            comp_mod.pip_position(session_with_two_tracks, 99, 0)

    def test_pip_position_invalid_clip(self, session_with_two_tracks):
        with pytest.raises(IndexError):
            comp_mod.pip_position(session_with_two_tracks, 2, 99)

    def test_pip_update_existing(self, session_with_two_tracks):
        comp_mod.pip_position(session_with_two_tracks, 2, 0,
                              x="10%", y="10%", width="40%", height="40%")
        result = comp_mod.pip_position(session_with_two_tracks, 2, 0,
                                       x="20%", y="20%", width="50%", height="50%")
        assert result["geometry"] == "20%/20%:50%x50%:100"

    def test_undo_set_blend_mode(self, session_with_two_tracks):
        comp_mod.set_track_blend_mode(session_with_two_tracks, 2, "multiply")
        assert comp_mod.get_track_blend_mode(session_with_two_tracks, 2)["blend_mode"] == "multiply"
        session_with_two_tracks.undo()
        assert comp_mod.get_track_blend_mode(session_with_two_tracks, 2)["blend_mode"] == "normal"

    def test_blend_mode_replaces_qtblend_with_cairolend(self, session_with_two_tracks):
        tractor = session_with_two_tracks.get_main_tractor()
        comp_trans = [t for t in tractor.findall("transition")
                      if get_property(t, "mlt_service") == "qtblend"
                      and get_property(t, "b_track") == "2"]
        assert len(comp_trans) == 1
        comp_mod.set_track_blend_mode(session_with_two_tracks, 2, "multiply")
        services = [get_property(t, "mlt_service") for t in tractor.findall("transition")]
        assert "frei0r.cairoblend" in services
        assert not any(get_property(t, "mlt_service") == "qtblend"
                       and get_property(t, "b_track") == "2"
                       for t in tractor.findall("transition"))

    def test_blend_mode_re_enables_first_video_track(self, session_with_track):
        comp_mod.set_track_blend_mode(session_with_track, 1, "multiply")
        tractor = session_with_track.get_main_tractor()
        for trans in tractor.findall("transition"):
            if (get_property(trans, "mlt_service") == "frei0r.cairoblend"
                    and get_property(trans, "b_track") == "1"):
                assert get_property(trans, "disable", "0") == "0"
                return
        pytest.fail("No cairolend transition found for track 1")

    def test_remove_lower_video_track_disables_qtblend(self, session):
        tl_mod.add_track(session, "video", "V1")
        tl_mod.add_track(session, "video", "V2")
        tl_mod.remove_track(session, 1)
        for trans in session.get_main_tractor().findall("transition"):
            if get_property(trans, "mlt_service") == "qtblend":
                assert get_property(trans, "disable", "0") == "1"



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
