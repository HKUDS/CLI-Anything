"""End-to-end tests for Openscreen CLI — requires ffmpeg installed.

These tests create real video files, run the full export pipeline,
and verify outputs with ffprobe.

Run with:
    python3 -m pytest cli_anything/openscreen/tests/test_full_e2e.py -v -s

Force installed CLI:
    CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest ... -v -s

Test classes:
    TestMediaE2E      - probe_real_video, check_video, check_invalid_video,
                        extract_thumbnail, extract_thumbnail_at_zero,
                        extract_frames, ffmpeg_and_ffprobe_found
    TestExportE2E     - basic_export, export_with_zoom, export_with_speed,
                        export_with_trim, export_complex,
                        export_no_video_raises, export_missing_video_raises
    TestCLISubprocess - cli_help, cli_version, cli_export_presets,
                        cli_media_probe, cli_project_new_json, cli_zoom_add,
                        cli_full_workflow, cli_media_check_valid,
                        cli_session_status
"""

import json
import os
import subprocess
import sys
import tempfile

import pytest

from cli_anything.openscreen.core.session import Session
from cli_anything.openscreen.core import project as proj_mod
from cli_anything.openscreen.core import timeline as tl_mod
from cli_anything.openscreen.core import export as export_mod
from cli_anything.openscreen.core import media as media_mod
from cli_anything.openscreen.core import preview as preview_mod
from cli_anything.openscreen.utils import ffmpeg_backend


# ── CLI resolver ───────────────────────────────────────────────────────────

def _resolve_cli(name: str):
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
        raise RuntimeError(
            f"{name} not found in PATH. Install with: pip install -e ."
        )
    module = "cli_anything.openscreen.openscreen_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


# ── Fixtures ──────────────────────────────────────────────────────────────

JPEG_MAGIC_PREFIX = b"\xff\xd8\xff"

@pytest.fixture(scope="module")
def test_video():
    """Create a 5-second test video with ffmpeg."""
    tmpdir = tempfile.mkdtemp()
    video_path = os.path.join(tmpdir, "test_recording.mp4")

    try:
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i",
            "testsrc=duration=5:size=1920x1080:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
            "-c:v", "libx264", "-c:a", "aac", "-shortest",
            video_path,
        ], capture_output=True, check=True, timeout=30)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("ffmpeg not available")

    yield video_path

    # Cleanup
    try:
        os.remove(video_path)
        os.rmdir(tmpdir)
    except OSError:
        pass


@pytest.fixture
def session(test_video):
    """Create a session with a project and test video attached."""
    s = Session()
    s.new_project(test_video)
    return s


def _artifact_path(manifest, artifact_id):
    for artifact in manifest["artifacts"]:
        if artifact["artifact_id"] == artifact_id:
            return os.path.join(manifest["_bundle_dir"], artifact["path"])
    raise KeyError(f"Artifact not found: {artifact_id}")


def _assert_jpeg(path):
    assert os.path.isfile(path), f"Missing JPEG artifact: {path}"
    with open(path, "rb") as fh:
        assert fh.read(3) == JPEG_MAGIC_PREFIX, f"Invalid JPEG header: {path}"
    assert os.path.getsize(path) > 0, f"Empty JPEG artifact: {path}"


# ── Media Tests ───────────────────────────────────────────────────────────

class TestMediaE2E:
    def test_probe_real_video(self, test_video):
        result = media_mod.probe(test_video)
        assert result["width"] == 1920
        assert result["height"] == 1080
        assert result["duration"] > 4.0
        assert result["codec"] == "h264"
        assert result["has_audio"] is True

    def test_check_video(self, test_video):
        result = media_mod.check_video(test_video)
        assert result["valid"] is True
        assert result["width"] == 1920

    def test_check_invalid_video(self):
        result = media_mod.check_video("/nonexistent/file.mp4")
        assert result["valid"] is False

    def test_extract_thumbnail(self, test_video):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            thumb_path = f.name
        try:
            result = media_mod.extract_thumbnail(test_video, thumb_path, time_s=1.0)
            assert os.path.exists(thumb_path)
            assert result["file_size"] > 0
        finally:
            os.unlink(thumb_path)

    def test_extract_thumbnail_at_zero(self, test_video):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            thumb_path = f.name
        try:
            result = media_mod.extract_thumbnail(test_video, thumb_path, time_s=0.0)
            assert os.path.exists(thumb_path)
            assert result["file_size"] > 0
        finally:
            os.unlink(thumb_path)

    def test_extract_frames(self, test_video):
        tmpdir = tempfile.mkdtemp()
        try:
            frames = ffmpeg_backend.extract_frames(test_video, tmpdir, fps=2, max_frames=10)
            assert len(frames) > 0
            assert all(f.endswith(".jpg") for f in frames)
            assert all(os.path.getsize(f) > 0 for f in frames)
        finally:
            import shutil
            shutil.rmtree(tmpdir)

    def test_ffmpeg_and_ffprobe_found(self):
        ffmpeg = ffmpeg_backend.find_ffmpeg()
        ffprobe = ffmpeg_backend.find_ffprobe()
        assert os.path.exists(ffmpeg)
        assert os.path.exists(ffprobe)
        print(f"\n  ffmpeg: {ffmpeg}")
        print(f"  ffprobe: {ffprobe}")


# ── Export Tests ──────────────────────────────────────────────────────────

class TestExportE2E:
    def test_basic_export(self, session):
        """Export with default settings (no regions)."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            out_path = f.name
        try:
            result = export_mod.render(session, out_path)
            assert os.path.exists(out_path)
            assert result["file_size"] > 0
            assert result["width"] > 0
            assert result["codec"] == "h264"
            assert result["segments_rendered"] >= 1
        finally:
            os.unlink(out_path)

    def test_export_with_zoom(self, session):
        """Export with a zoom region."""
        tl_mod.add_zoom_region(session, 1000, 3000, depth=3, focus_x=0.7, focus_y=0.3)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            out_path = f.name
        try:
            result = export_mod.render(session, out_path)
            assert os.path.exists(out_path)
            assert result["file_size"] > 0
            assert result["segments_rendered"] >= 2  # before, during, after zoom
        finally:
            os.unlink(out_path)

    def test_export_with_speed(self, session):
        """Export with a speed region."""
        tl_mod.add_speed_region(session, 2000, 4000, speed=2.0)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            out_path = f.name
        try:
            result = export_mod.render(session, out_path)
            assert os.path.exists(out_path)
            assert result["file_size"] > 0
            # Output should be shorter than source due to 2x speed section
            assert result["duration"] < 5.0
        finally:
            os.unlink(out_path)

    def test_export_with_trim(self, session):
        """Export with a trim region."""
        tl_mod.add_trim_region(session, 0, 1000)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            out_path = f.name
        try:
            result = export_mod.render(session, out_path)
            assert os.path.exists(out_path)
            # Should be shorter due to trimmed 1 second
            assert result["duration"] < 5.0
        finally:
            os.unlink(out_path)

    def test_export_complex(self, session):
        """Export with multiple regions and settings."""
        proj_mod.set_setting(session, "padding", 40)
        proj_mod.set_setting(session, "wallpaper", "solid_dark")

        tl_mod.add_zoom_region(session, 500, 2000, depth=4, focus_x=0.5, focus_y=0.5)
        tl_mod.add_speed_region(session, 3000, 4500, speed=1.5)
        tl_mod.add_trim_region(session, 0, 200)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            out_path = f.name
        try:
            result = export_mod.render(session, out_path)
            assert os.path.exists(out_path)
            assert result["file_size"] > 0
            assert result["width"] == 1920
            assert result["height"] == 1080
        finally:
            os.unlink(out_path)

    def test_export_no_video_raises(self):
        """Export fails if no source video is set."""
        s = Session()
        s.new_project()
        with pytest.raises(Exception):
            export_mod.render(s, "/tmp/out.mp4")

    def test_export_missing_video_raises(self):
        """Export fails if source video file is missing."""
        import tempfile as _tempfile
        with _tempfile.TemporaryDirectory() as tmp_dir:
            s = Session()
            s.new_project(video_path="/tmp/nonexistent_12345.mp4")
            with pytest.raises(Exception):
                export_mod.render(s, os.path.join(tmp_dir, "out.mp4"))


class TestPreviewE2E:
    def test_capture_preview_bundle(self, session):
        tl_mod.add_zoom_region(session, 800, 2400, depth=2, focus_x=0.65, focus_y=0.35)
        tl_mod.add_speed_region(session, 2500, 3800, speed=1.5)

        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = os.path.join(tmp_dir, "preview.openscreen")
            proj_mod.save_project(session, project_path)

            manifest = preview_mod.capture(session, root_dir=tmp_dir, force=True)
            assert manifest["software"] == "openscreen"
            assert manifest["bundle_kind"] == "capture"
            assert manifest["status"] in ("ok", "partial")

            clip_path = _artifact_path(manifest, "clip")
            hero_path = _artifact_path(manifest, "frame_03")
            probe = media_mod.probe(clip_path)

            assert os.path.isfile(clip_path)
            assert os.path.getsize(clip_path) > 0
            assert probe["width"] > 0
            assert probe["height"] > 0
            assert probe["duration"] > 0
            _assert_jpeg(hero_path)

            latest = preview_mod.latest(project_path=project_path, recipe="quick", root_dir=tmp_dir)
            assert latest["bundle_id"] == manifest["bundle_id"]

            print(f"\n  Openscreen preview bundle: {manifest['_bundle_dir']}")
            print(f"  Openscreen preview clip: {clip_path}")
            print(f"  Openscreen preview hero: {hero_path}")


# ── CLI Subprocess Tests ──────────────────────────────────────────────────

class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-openscreen")

    def _run(self, args, check=True, timeout=30):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
            timeout=timeout,
            check=check,
        )

    def test_cli_help(self):
        result = self._run(["--help"], check=False)
        assert result.returncode == 0
        assert "Openscreen CLI" in result.stdout

    def test_cli_version(self):
        result = self._run(["--version"], check=False)
        assert result.returncode == 0
        assert "1.0.0" in result.stdout

    def test_cli_export_presets(self):
        result = self._run(["--json", "export", "presets"], check=False)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_cli_media_probe(self, test_video):
        result = self._run(["--json", "media", "probe", test_video], check=False)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["width"] == 1920

    def test_cli_project_new_json(self):
        """CLI project new --json returns project info."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            proj_path = os.path.join(tmp_dir, "cli_test.openscreen")
            result = self._run(["--json", "project", "new", "-o", proj_path], check=False)
            assert result.returncode == 0

            data = json.loads(result.stdout)
            assert data.get("status") == "created"
            assert "saved_to" in data
            assert os.path.exists(proj_path)
            print(f"\n  Project created: {proj_path}")

    def test_cli_zoom_add(self):
        """CLI zoom add works and persists to file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            proj_path = os.path.join(tmp_dir, "zoom_test.openscreen")
            # Create project
            self._run(["project", "new", "-o", proj_path], check=False)

            # Add zoom
            result = self._run([
                "--json", "--project", proj_path,
                "zoom", "add",
                "--start", "1000", "--end", "3000", "--depth", "3",
            ], check=False)
            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert data["depth"] == 3
            assert data["startMs"] == 1000

            # Verify saved
            result2 = self._run(
                ["--json", "--project", proj_path, "zoom", "list"], check=False
            )
            assert result2.returncode == 0
            print(f"\n  Zoom add result: depth={data['depth']}, id={data['id']}")

    def test_cli_full_workflow(self, test_video):
        """Full CLI workflow: create project, add regions, export."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            proj_path = os.path.join(tmp_dir, "workflow.openscreen")
            output_path = os.path.join(tmp_dir, "workflow_output.mp4")

            # 1. Create project with video
            result = self._run(
                ["project", "new", "-v", test_video, "-o", proj_path], check=False
            )
            assert result.returncode == 0
            assert os.path.exists(proj_path)

            # 2. Add zoom region
            result = self._run([
                "--project", proj_path,
                "zoom", "add",
                "--start", "1000", "--end", "2000", "--depth", "2",
            ], check=False)
            assert result.returncode == 0

            # 3. Set quality
            result = self._run([
                "--project", proj_path,
                "project", "set", "exportQuality", "medium",
            ], check=False)
            assert result.returncode == 0

            # 4. Export
            result = self._run([
                "--json", "--project", proj_path,
                "export", "render", output_path,
            ], check=False)
            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert os.path.exists(output_path)
            assert data["file_size"] > 1000

            # 5. Probe output
            result = self._run(
                ["--json", "media", "probe", output_path], check=False
            )
            assert result.returncode == 0
            probe_data = json.loads(result.stdout)
            assert probe_data["width"] > 0
            assert probe_data["duration"] > 0

            print(f"\n  Full workflow output: {output_path}")
            print(f"    Size: {data['file_size']:,} bytes")
            print(f"    Duration: {data['duration']:.2f}s")
            print(f"    Dimensions: {probe_data['width']}x{probe_data['height']}")

    def test_cli_media_check_valid(self, test_video):
        """CLI media check returns valid=True for a real video."""
        result = self._run(["--json", "media", "check", test_video], check=False)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["valid"] is True

    def test_cli_session_status(self):
        """CLI session status works."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            proj_path = os.path.join(tmp_dir, "status_test.openscreen")
            self._run(["project", "new", "-o", proj_path], check=False)

            result = self._run(
                ["--json", "--project", proj_path, "session", "status"], check=False
            )
            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert "project_open" in data
            assert "undo_available" in data

    def test_cli_preview_capture(self, test_video):
        with tempfile.TemporaryDirectory() as tmp_dir:
            proj_path = os.path.join(tmp_dir, "preview.openscreen")

            result = self._run(
                ["project", "new", "-v", test_video, "-o", proj_path],
                check=False,
                timeout=60,
            )
            assert result.returncode == 0

            self._run(
                [
                    "--project",
                    proj_path,
                    "zoom",
                    "add",
                    "--start",
                    "700",
                    "--end",
                    "2200",
                    "--depth",
                    "2",
                ],
                check=False,
                timeout=60,
            )

            result = self._run(
                [
                    "--json",
                    "--project",
                    proj_path,
                    "preview",
                    "capture",
                    "--root-dir",
                    tmp_dir,
                ],
                check=False,
                timeout=180,
            )
            assert result.returncode == 0, result.stderr

            manifest = json.loads(result.stdout)
            assert manifest["software"] == "openscreen"
            clip_path = _artifact_path(manifest, "clip")
            hero_path = _artifact_path(manifest, "frame_03")
            assert os.path.isfile(clip_path)
            _assert_jpeg(hero_path)

            latest = self._run(
                [
                    "--json",
                    "preview",
                    "latest",
                    "--recipe",
                    "quick",
                    "--root-dir",
                    tmp_dir,
                ],
                check=False,
                timeout=60,
            )
            assert latest.returncode == 0, latest.stderr
            latest_manifest = json.loads(latest.stdout)
            assert latest_manifest["bundle_id"] == manifest["bundle_id"]

            print(f"\n  Openscreen preview bundle: {manifest['_bundle_dir']}")
            print(f"  Openscreen preview clip: {clip_path}")
            print(f"  Openscreen preview hero: {hero_path}")
