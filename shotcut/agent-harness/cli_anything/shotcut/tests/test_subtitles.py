"""Tests for timestamped subtitle rendering."""

import json

from cli_anything.shotcut.core.subtitles.models import SubtitleRequest
from cli_anything.shotcut.core.subtitles.service import SubtitleService


def test_subtitle_service_generates_bold_centered_ass(tmp_path):
    video = tmp_path / "video.mp4"
    transcript = tmp_path / "video.transcript.json"
    output = tmp_path / "subtitled.mp4"
    video.write_bytes(b"video")
    transcript.write_text(
        json.dumps(
            {
                "segments": [
                    {"start_seconds": 0, "end_seconds": 1.25, "text": "Hello {world}"}
                ]
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    class FakeRenderer:
        def render(self, video_path, ass_path, output_path, overwrite):
            captured["video_path"] = video_path
            captured["ass"] = ass_path.read_text(encoding="utf-8")
            captured["output_path"] = output_path
            captured["overwrite"] = overwrite

    result = SubtitleService(FakeRenderer()).add_subtitles(
        SubtitleRequest(video, transcript, output, overwrite=True)
    )

    assert result.subtitle_count == 1
    assert "Default,Arial,64" in captured["ass"]
    assert ",-1,0,0,0,100,100" in captured["ass"]
    assert "Alignment, MarginL" in captured["ass"]
    assert "Dialogue: 0,0:00:00.00,0:00:01.25" in captured["ass"]
    assert r"Hello \{world\}" in captured["ass"]
    assert captured["overwrite"] is True


def test_subtitle_service_rejects_empty_transcript(tmp_path):
    video = tmp_path / "video.mp4"
    transcript = tmp_path / "transcript.json"
    video.write_bytes(b"video")
    transcript.write_text(json.dumps({"segments": []}), encoding="utf-8")

    try:
        SubtitleService(object()).add_subtitles(
            SubtitleRequest(video, transcript, tmp_path / "out.mp4")
        )
    except ValueError as error:
        assert "no subtitle segments" in str(error)
    else:
        raise AssertionError("Expected empty transcripts to be rejected")
