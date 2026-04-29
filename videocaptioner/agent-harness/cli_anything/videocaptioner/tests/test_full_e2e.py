"""End-to-end tests for VideoCaptioner CLI harness.

These tests require videocaptioner to be installed.
Skip with: pytest -m "not e2e"
"""

import pytest
import subprocess
import shutil

# Skip all tests if videocaptioner is not installed
pytestmark = pytest.mark.skipif(
    shutil.which("videocaptioner") is None,
    reason="videocaptioner not installed"
)


class TestCLIEntryPoint:
    def test_help(self):
        result = subprocess.run(
            ["videocaptioner", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "transcribe" in result.stdout
        assert "subtitle" in result.stdout
        assert "synthesize" in result.stdout

    def test_version(self):
        result = subprocess.run(
            ["videocaptioner", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "videocaptioner" in result.stdout

    def test_config_show(self):
        result = subprocess.run(
            ["videocaptioner", "config", "show"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0

    def test_transcribe_missing_file(self):
        result = subprocess.run(
            ["videocaptioner", "transcribe", "nonexistent.mp4", "--asr", "bijian"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 3  # FILE_NOT_FOUND

    def test_subtitle_missing_file(self):
        result = subprocess.run(
            ["videocaptioner", "subtitle", "nonexistent.srt"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 3

    def test_synthesize_missing_args(self):
        result = subprocess.run(
            ["videocaptioner", "synthesize", "video.mp4"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 2  # USAGE_ERROR (missing -s)

    def test_invalid_asr_engine(self):
        result = subprocess.run(
            ["videocaptioner", "transcribe", "video.mp4", "--asr", "invalid"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 2

    def test_invalid_target_language(self):
        result = subprocess.run(
            ["videocaptioner", "subtitle", "test.srt", "--translator", "bing",
             "--target-language", "invalid-lang"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0


class TestBackendIntegration:
    def test_get_version(self):
        from cli_anything.videocaptioner.utils.vc_backend import get_version
        version = get_version()
        assert "videocaptioner" in version.lower()

    def test_get_config(self):
        from cli_anything.videocaptioner.utils.vc_backend import get_config
        config = get_config()
        assert "llm" in config or "transcribe" in config

    def test_get_styles(self):
        from cli_anything.videocaptioner.utils.vc_backend import get_styles
        styles = get_styles()
        assert styles
