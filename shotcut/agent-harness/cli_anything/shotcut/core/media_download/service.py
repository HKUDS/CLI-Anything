"""Generic media download application service."""

from .models import DownloadRequest, DownloadResult
from .ports import FileDownloader
from .registry import MediaResolverRegistry


class MediaDownloadService:
    """Resolve a platform URL and download its direct media resource."""

    def __init__(
        self,
        resolver_registry: MediaResolverRegistry,
        file_downloader: FileDownloader,
    ) -> None:
        self._resolver_registry = resolver_registry
        self._file_downloader = file_downloader

    def download(self, request: DownloadRequest) -> DownloadResult:
        if not request.source_url.strip():
            raise ValueError("Media source URL cannot be empty")

        resolved_media = self._resolver_registry.resolve(request.source_url)
        output_path = self._file_downloader.download(
            resolved_media.media_url,
            request.output_path,
            request.overwrite,
        )
        return DownloadResult(
            source_url=resolved_media.source_url,
            output_path=output_path,
            platform=resolved_media.platform,
            media_type=resolved_media.media_type,
        )
