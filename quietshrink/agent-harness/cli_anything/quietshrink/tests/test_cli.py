"""Smoke tests for the cli-anything-quietshrink harness.

The harness is a thin Python wrapper around the standalone quietshrink bash
CLI. The bash CLI itself is tested upstream
(https://github.com/achiya-automation/quietshrink/blob/main/tests/test_cli.sh).

These tests exercise the harness layer: command wiring, JSON output schema,
error paths, and the subprocess interface — all without invoking ffmpeg.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli_anything.quietshrink import __version__
from cli_anything.quietshrink.quietshrink_cli import cli, find_bash_cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestVersionAndHelp:
    def test_version_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_help_lists_all_subcommands(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        for subcommand in ("compress", "probe", "presets", "doctor"):
            assert subcommand in result.output

    def test_no_args_shows_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "Usage" in result.output or "usage" in result.output


class TestPresets:
    def test_presets_text_output(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["presets"])
        assert result.exit_code == 0
        for name in ("tiny", "balanced", "transparent", "pristine"):
            assert name in result.output

    def test_presets_json_schema(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["presets", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "presets" in data
        assert len(data["presets"]) == 4

        names = {p["name"] for p in data["presets"]}
        assert names == {"tiny", "balanced", "transparent", "pristine"}

        for preset in data["presets"]:
            assert {"name", "q_value", "typical_reduction", "ssim", "use_case"} <= preset.keys()
            assert isinstance(preset["q_value"], int)


class TestFindBashCli:
    def test_uses_path_when_available(self, tmp_path: Path) -> None:
        fake_bin = tmp_path / "quietshrink"
        fake_bin.write_text("#!/bin/bash\necho fake")
        fake_bin.chmod(0o755)

        with patch("shutil.which", return_value=str(fake_bin)):
            assert find_bash_cli() == fake_bin

    def test_raises_when_missing(self) -> None:
        from click import ClickException

        with patch("shutil.which", return_value=None):
            with pytest.raises(ClickException) as exc_info:
                find_bash_cli()
            assert "not found" in str(exc_info.value.message).lower()
            assert "install" in str(exc_info.value.message).lower()


class TestDoctor:
    @patch("shutil.which")
    @patch("subprocess.run")
    def test_doctor_all_ok_json(self, mock_run: MagicMock, mock_which: MagicMock, runner: CliRunner) -> None:
        mock_which.side_effect = lambda name: f"/usr/local/bin/{name}"
        mock_run.return_value = MagicMock(returncode=0, stdout="hevc_videotoolbox", stderr="")

        result = runner.invoke(cli, ["doctor", "--json"])
        data = json.loads(result.output)
        assert "checks" in data
        assert "ready" in data
        assert isinstance(data["ready"], bool)

    @patch("shutil.which", return_value=None)
    def test_doctor_no_ffmpeg_json(self, _mock_which: MagicMock, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["doctor", "--json"])
        data = json.loads(result.output)
        assert data["ready"] is False
        ffmpeg_check = next(c for c in data["checks"] if c["check"] == "ffmpeg installed")
        assert ffmpeg_check["ok"] is False


class TestProbe:
    @patch("shutil.which", return_value=None)
    def test_probe_no_ffprobe(self, _mock_which: MagicMock, runner: CliRunner, tmp_path: Path) -> None:
        sample = tmp_path / "sample.mov"
        sample.write_bytes(b"fake-mov-data")

        result = runner.invoke(cli, ["probe", str(sample), "--json"])
        assert result.exit_code == 2
        data = json.loads(result.output)
        assert "error" in data
        assert "ffprobe" in data["error"]

    @patch("shutil.which", return_value="/usr/local/bin/ffprobe")
    @patch("subprocess.run")
    def test_probe_returns_metadata(
        self, mock_run: MagicMock, _mock_which: MagicMock, runner: CliRunner, tmp_path: Path,
    ) -> None:
        sample = tmp_path / "rec.mov"
        sample.write_bytes(b"x" * 1024)

        ffprobe_output = {
            "streams": [{"codec_name": "h264", "width": 1920, "height": 1080, "r_frame_rate": "60/1"}],
            "format": {"duration": "12.5", "bit_rate": "5000000", "size": "1024"},
        }
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(ffprobe_output), stderr="")

        result = runner.invoke(cli, ["probe", str(sample), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["codec"] == "h264"
        assert data["width"] == 1920
        assert data["height"] == 1080
        assert data["duration_seconds"] == 12.5
        assert data["size_bytes"] == 1024

    def test_probe_missing_file_errors(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["probe", "/does/not/exist.mov"])
        assert result.exit_code != 0


class TestCompress:
    @patch("cli_anything.quietshrink.quietshrink_cli.find_bash_cli")
    @patch("subprocess.run")
    def test_compress_emits_bash_json(
        self, mock_run: MagicMock, mock_find: MagicMock, runner: CliRunner, tmp_path: Path,
    ) -> None:
        mock_find.return_value = Path("/fake/quietshrink")
        sample = tmp_path / "rec.mov"
        sample.write_bytes(b"x" * 1024)

        bash_response = {
            "input": str(sample),
            "output": str(tmp_path / "out.mov"),
            "input_size": 1024,
            "output_size": 256,
            "saved_percent": 75.0,
            "quality_preset": "transparent",
            "q_value": 60,
        }
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(bash_response), stderr="")

        result = runner.invoke(cli, ["compress", str(sample), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["quality_preset"] == "transparent"
        assert data["saved_percent"] == 75.0

    @patch("cli_anything.quietshrink.quietshrink_cli.find_bash_cli")
    @patch("subprocess.run")
    def test_compress_passes_quality_flag(
        self, mock_run: MagicMock, mock_find: MagicMock, runner: CliRunner, tmp_path: Path,
    ) -> None:
        mock_find.return_value = Path("/fake/quietshrink")
        sample = tmp_path / "rec.mov"
        sample.write_bytes(b"x")

        mock_run.return_value = MagicMock(returncode=0, stdout='{"saved_percent": 90}', stderr="")

        result = runner.invoke(cli, ["compress", str(sample), "-q", "tiny", "--json"])
        assert result.exit_code == 0
        invoked_args = mock_run.call_args[0][0]
        assert "--quality" in invoked_args
        assert "tiny" in invoked_args

    @patch("cli_anything.quietshrink.quietshrink_cli.find_bash_cli")
    @patch("subprocess.run")
    def test_compress_handles_bash_failure(
        self, mock_run: MagicMock, mock_find: MagicMock, runner: CliRunner, tmp_path: Path,
    ) -> None:
        mock_find.return_value = Path("/fake/quietshrink")
        sample = tmp_path / "rec.mov"
        sample.write_bytes(b"x")

        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["quietshrink"], stderr="ffmpeg crashed",
        )

        result = runner.invoke(cli, ["compress", str(sample), "--json"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error"] == "compression_failed"
        assert "ffmpeg crashed" in data["stderr"]
