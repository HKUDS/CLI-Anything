"""CLI wiring tests for Instagram media downloads."""

import json

from click.testing import CliRunner

from cli_anything.shotcut import shotcut_cli
from cli_anything.shotcut.core.media_download.models import DownloadResult


def test_download_instagram_outputs_json(monkeypatch, tmp_path):
    captured = {}

    class FakeService:
        def __init__(self, **dependencies):
            captured["dependencies"] = dependencies

        def download(self, request):
            captured["request"] = request
            return DownloadResult(
                source_url=request.source_url,
                output_path=request.output_path.resolve(),
                platform="instagram",
                media_type="video",
            )

    monkeypatch.setattr(shotcut_cli, "MediaDownloadService", FakeService)
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "test-key")
    output_path = tmp_path / "competitor.mp4"

    result = CliRunner().invoke(
        shotcut_cli.cli,
        [
            "--json",
            "media",
            "download-instagram",
            "https://www.instagram.com/p/example/",
            "-o",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["platform"] == "instagram"
    assert captured["request"].source_url.endswith("/p/example/")
    assert captured["request"].overwrite is False
