"""Tests for the platform-neutral media download service."""

from pathlib import Path

from cli_anything.shotcut.core.media_download.models import (
    DownloadRequest,
    ResolvedMedia,
)
from cli_anything.shotcut.core.media_download.registry import MediaResolverRegistry
from cli_anything.shotcut.core.media_download.service import MediaDownloadService


class FakeResolver:
    platform = "fake"

    def can_resolve(self, source_url: str) -> bool:
        return source_url.startswith("fake:")

    def resolve(self, source_url: str) -> ResolvedMedia:
        return ResolvedMedia(source_url, "https://cdn.test/video.mp4", self.platform)


class FakeDownloader:
    def __init__(self) -> None:
        self.calls = []

    def download(self, source_url: str, output_path: Path, overwrite: bool = False) -> Path:
        self.calls.append((source_url, output_path, overwrite))
        return output_path.resolve()


def test_service_resolves_then_downloads_media(tmp_path):
    downloader = FakeDownloader()
    service = MediaDownloadService(
        resolver_registry=MediaResolverRegistry([FakeResolver()]),
        file_downloader=downloader,
    )

    result = service.download(
        DownloadRequest(
            source_url="fake:video",
            output_path=tmp_path / "video.mp4",
            overwrite=True,
        )
    )

    assert result.platform == "fake"
    assert result.output_path == (tmp_path / "video.mp4").resolve()
    assert downloader.calls == [
        ("https://cdn.test/video.mp4", tmp_path / "video.mp4", True)
    ]
