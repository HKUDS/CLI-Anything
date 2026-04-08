"""Unit tests for VideoCaptioner CLI harness core modules."""

import pytest
from unittest.mock import patch, MagicMock


class TestTranscribe:
    @patch("cli_anything.videocaptioner.core.transcribe.run_quiet", return_value="/tmp/o.srt")
    def test_basic(self, mock_run):
        from cli_anything.videocaptioner.core.transcribe import transcribe
        assert transcribe("video.mp4") == "/tmp/o.srt"
        assert "transcribe" in mock_run.call_args[0][0]
        assert "bijian" in mock_run.call_args[0][0]

    @patch("cli_anything.videocaptioner.core.transcribe.run_quiet", return_value="/tmp/o.json")
    def test_options(self, mock_run):
        from cli_anything.videocaptioner.core.transcribe import transcribe
        transcribe("v.mp4", asr="whisper-api", language="fr", format="json",
                   output_path="/tmp/o.json", whisper_api_key="sk-xxx")
        a = mock_run.call_args[0][0]
        assert "whisper-api" in a and "fr" in a and "json" in a and "sk-xxx" in a

    @patch("cli_anything.videocaptioner.core.transcribe.run_quiet", return_value="/tmp/o.srt")
    def test_word_timestamps(self, mock_run):
        from cli_anything.videocaptioner.core.transcribe import transcribe
        transcribe("v.mp4", word_timestamps=True)
        assert "--word-timestamps" in mock_run.call_args[0][0]


class TestSubtitle:
    @patch("cli_anything.videocaptioner.core.subtitle.run_quiet", return_value="/tmp/o.srt")
    def test_translate(self, mock_run):
        from cli_anything.videocaptioner.core.subtitle import process_subtitle
        process_subtitle("in.srt", translator="bing", target_language="en")
        a = mock_run.call_args[0][0]
        assert "bing" in a and "en" in a

    @patch("cli_anything.videocaptioner.core.subtitle.run_quiet", return_value="/tmp/o.srt")
    def test_skip(self, mock_run):
        from cli_anything.videocaptioner.core.subtitle import process_subtitle
        process_subtitle("in.srt", no_optimize=True, no_translate=True)
        a = mock_run.call_args[0][0]
        assert "--no-optimize" in a and "--no-translate" in a

    @patch("cli_anything.videocaptioner.core.subtitle.run_quiet", return_value="/tmp/o.srt")
    def test_llm(self, mock_run):
        from cli_anything.videocaptioner.core.subtitle import process_subtitle
        process_subtitle("in.srt", translator="llm", target_language="ja",
                        reflect=True, api_key="sk-xxx", layout="target-above")
        a = mock_run.call_args[0][0]
        assert "--reflect" in a and "sk-xxx" in a and "target-above" in a


class TestSynthesize:
    @patch("cli_anything.videocaptioner.core.synthesize.run_quiet", return_value="/tmp/o.mp4")
    def test_soft(self, mock_run):
        from cli_anything.videocaptioner.core.synthesize import synthesize
        synthesize("v.mp4", "s.srt")
        assert "soft" in mock_run.call_args[0][0]

    @patch("cli_anything.videocaptioner.core.synthesize.run_quiet", return_value="/tmp/o.mp4")
    def test_hard_style(self, mock_run):
        from cli_anything.videocaptioner.core.synthesize import synthesize
        synthesize("v.mp4", "s.srt", subtitle_mode="hard", style="anime", quality="high")
        a = mock_run.call_args[0][0]
        assert "hard" in a and "anime" in a and "high" in a

    @patch("cli_anything.videocaptioner.core.synthesize.run_quiet", return_value="/tmp/o.mp4")
    def test_rounded(self, mock_run):
        from cli_anything.videocaptioner.core.synthesize import synthesize
        synthesize("v.mp4", "s.srt", subtitle_mode="hard", render_mode="rounded",
                  style_override='{"bg_color":"#000000cc"}')
        a = mock_run.call_args[0][0]
        assert "rounded" in a and "#000000cc" in str(a)


class TestPipeline:
    @patch("cli_anything.videocaptioner.core.pipeline.run_quiet", return_value="/tmp/o.mp4")
    def test_full(self, mock_run):
        from cli_anything.videocaptioner.core.pipeline import process
        process("v.mp4", translator="bing", target_language="en", style="anime")
        a = mock_run.call_args[0][0]
        assert "process" in a and "bing" in a and "anime" in a

    @patch("cli_anything.videocaptioner.core.pipeline.run_quiet", return_value="/tmp/o.srt")
    def test_no_synth(self, mock_run):
        from cli_anything.videocaptioner.core.pipeline import process
        process("v.mp4", no_synthesize=True)
        assert "--no-synthesize" in mock_run.call_args[0][0]


class TestBackend:
    @patch("subprocess.run")
    def test_success(self, mock_sub):
        mock_sub.return_value = MagicMock(returncode=0, stdout="/tmp/o.srt\n", stderr="")
        from cli_anything.videocaptioner.utils.vc_backend import run_quiet
        assert run_quiet(["transcribe", "v.mp4"]) == "/tmp/o.srt"

    @patch("subprocess.run")
    def test_failure(self, mock_sub):
        mock_sub.return_value = MagicMock(returncode=5, stdout="", stderr="Error: fail")
        from cli_anything.videocaptioner.utils.vc_backend import run_quiet
        with pytest.raises(RuntimeError, match="fail"):
            run_quiet(["transcribe", "x.mp4"])

    @patch("shutil.which", return_value=None)
    def test_not_installed(self, _):
        from cli_anything.videocaptioner.utils.vc_backend import _find_vc
        with pytest.raises(RuntimeError, match="not found"):
            _find_vc()
