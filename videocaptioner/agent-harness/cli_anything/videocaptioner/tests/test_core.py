"""Unit tests for VideoCaptioner CLI harness core modules."""

import pytest
from unittest.mock import patch, MagicMock
import sys


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
    def test_hard_quality_output(self, mock_run):
        from cli_anything.videocaptioner.core.synthesize import synthesize
        synthesize("v.mp4", "s.srt", subtitle_mode="hard", quality="high", output_path="/tmp/o.mp4")
        a = mock_run.call_args[0][0]
        assert "hard" in a and "high" in a and "/tmp/o.mp4" in a

    @patch("cli_anything.videocaptioner.core.synthesize.run_quiet", return_value="/tmp/o.mp4")
    def test_compatibility_args_ignored(self, mock_run):
        from cli_anything.videocaptioner.core.synthesize import synthesize
        synthesize(
            "v.mp4",
            "s.srt",
            subtitle_mode="hard",
            layout="target-above",
            render_mode="rounded",
            style="anime",
            style_override='{"bg_color":"#000000cc"}',
            font_file="/tmp/font.ttf",
        )
        a = mock_run.call_args[0][0]
        assert "--layout" not in a
        assert "--render-mode" not in a
        assert "--style" not in a
        assert "--style-override" not in a
        assert "--font-file" not in a

    @patch("cli_anything.videocaptioner.core.synthesize.ensure_subtitle_consistency")
    @patch("cli_anything.videocaptioner.core.synthesize.run_quiet", return_value="/tmp/o.mp4")
    def test_review_script_blocks_before_burn(self, mock_run, mock_review):
        from cli_anything.videocaptioner.core.synthesize import synthesize
        synthesize("v.mp4", "s.srt", review_script="approved.txt", max_script_diff_ratio=0.2)
        mock_review.assert_called_once_with("s.srt", "approved.txt", max_diff_ratio=0.2)
        assert mock_run.called


class TestPipeline:
    @patch("cli_anything.videocaptioner.core.pipeline.run_quiet", return_value="/tmp/o.mp4")
    def test_full(self, mock_run):
        from cli_anything.videocaptioner.core.pipeline import process
        process("v.mp4", translator="bing", target_language="en", layout="target-above")
        a = mock_run.call_args[0][0]
        assert "process" in a and "bing" in a and "target-above" in a

    @patch("cli_anything.videocaptioner.core.pipeline.run_quiet", return_value="/tmp/o.srt")
    def test_no_synth(self, mock_run):
        from cli_anything.videocaptioner.core.pipeline import process
        process("v.mp4", no_synthesize=True)
        assert "--no-synthesize" in mock_run.call_args[0][0]

    @patch("cli_anything.videocaptioner.core.pipeline.run_quiet", return_value="/tmp/o.mp4")
    def test_compatibility_style_args_ignored(self, mock_run):
        from cli_anything.videocaptioner.core.pipeline import process
        process("v.mp4", style="anime", style_override="{}", render_mode="rounded")
        a = mock_run.call_args[0][0]
        assert "--style" not in a
        assert "--style-override" not in a
        assert "--render-mode" not in a


class TestBackend:
    @patch("cli_anything.videocaptioner.utils.vc_backend._find_vc", return_value="/usr/bin/videocaptioner")
    @patch("subprocess.run")
    def test_success(self, mock_sub, _mock_find):
        mock_sub.return_value = MagicMock(returncode=0, stdout="/tmp/o.srt\n", stderr="")
        from cli_anything.videocaptioner.utils.vc_backend import run_quiet
        assert run_quiet(["transcribe", "v.mp4"]) == "/tmp/o.srt"

    @patch("cli_anything.videocaptioner.utils.vc_backend._find_vc", return_value="/usr/bin/videocaptioner")
    @patch("subprocess.run")
    def test_failure(self, mock_sub, _mock_find):
        mock_sub.return_value = MagicMock(returncode=5, stdout="", stderr="Error: fail")
        from cli_anything.videocaptioner.utils.vc_backend import run_quiet
        with pytest.raises(RuntimeError, match="fail"):
            run_quiet(["transcribe", "x.mp4"])

    @patch("shutil.which", return_value=None)
    def test_not_installed(self, _):
        from cli_anything.videocaptioner.utils.vc_backend import _find_vc
        with pytest.raises(RuntimeError, match="not found"):
            _find_vc()

    @patch("cli_anything.videocaptioner.utils.vc_backend.has_subcommand", return_value=False)
    @patch("cli_anything.videocaptioner.utils.vc_backend.get_version", return_value="videocaptioner 1.4.1")
    def test_get_styles_fallback(self, _mock_version, _mock_has_subcommand):
        from cli_anything.videocaptioner.utils.vc_backend import get_styles
        styles = get_styles()
        assert "does not expose a 'style' subcommand" in styles

    def test_runtime_guidance(self):
        from cli_anything.videocaptioner.utils.vc_backend import get_runtime_guidance
        guidance = get_runtime_guidance()
        assert guidance["upstream_requires_python"] == ">=3.10,<3.13"
        assert guidance["python_runtime"].startswith(f"{sys.version_info.major}.{sys.version_info.minor}")


class TestReview:
    def test_review_report_passes_for_matching_script(self, tmp_path):
        subtitle_path = tmp_path / "matching.srt"
        script_path = tmp_path / "matching.txt"
        subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nDark mode ships today.\n", encoding="utf-8")
        script_path.write_text("Dark mode ships today.", encoding="utf-8")

        from cli_anything.videocaptioner.core.review import build_review_report
        report = build_review_report(str(subtitle_path), script_path=str(script_path))
        assert report["status"] == "pass"
        assert report["diff_ratio"] == 0.0

    def test_review_report_flags_mismatch(self, tmp_path):
        subtitle_path = tmp_path / "mismatch.srt"
        script_path = tmp_path / "mismatch.txt"
        subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nship stark mode today\n", encoding="utf-8")
        script_path.write_text("ships dark mode today", encoding="utf-8")

        from cli_anything.videocaptioner.core.review import ensure_subtitle_consistency
        with pytest.raises(RuntimeError, match="Subtitle/script review failed"):
            ensure_subtitle_consistency(str(subtitle_path), str(script_path), max_diff_ratio=0.1)

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("subprocess.run")
    def test_render_preview_frame(self, mock_run, _mock_which, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        video_path = tmp_path / "video.mp4"
        subtitle_path = tmp_path / "sub.srt"
        output_path = tmp_path / "preview.png"
        video_path.write_bytes(b"video")
        subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")

        from cli_anything.videocaptioner.core.review import render_preview_frame
        result = render_preview_frame(
            str(video_path),
            str(subtitle_path),
            at="00:00:05.000",
            output_path=str(output_path),
        )
        assert result == str(output_path)
        assert "-vf" in mock_run.call_args[0][0]
