"""BrightData-backed Instagram video resolver."""

from urllib.parse import urlparse

from ...models import ResolvedMedia
from ...ports import BrightDataApi


class BrightDataInstagramVideoResolver:
    platform = "instagram"
    INSTAGRAM_POST_DATASET = "gd_lk5ns7kz21pck8jpis"
    INSTAGRAM_REEL_DATASET = "gd_lyclm20il4r5helnj"

    def __init__(self, brightdata_api: BrightDataApi) -> None:
        self._brightdata_api = brightdata_api

    def can_resolve(self, source_url: str) -> bool:
        parsed = urlparse(source_url)
        hostname = (parsed.hostname or "").lower()
        path = parsed.path.rstrip("/")
        return (
            hostname == "instagram.com" or hostname.endswith(".instagram.com")
        ) and any(path.startswith(prefix) for prefix in ("/p/", "/reel/", "/reels/"))

    def resolve(self, source_url: str) -> ResolvedMedia:
        normalized_url, dataset_id = self._normalize_source(source_url)
        snapshot_id = self._brightdata_api.trigger(dataset_id, normalized_url)
        records = self._brightdata_api.wait_for_snapshot(snapshot_id)
        media_url = self._find_video_url(records)
        return ResolvedMedia(
            source_url=source_url,
            media_url=media_url,
            platform=self.platform,
        )

    def _normalize_source(self, source_url: str) -> tuple[str, str]:
        parsed = urlparse(source_url)
        path = parsed.path.replace("/reels/", "/reel/", 1)
        normalized_url = parsed._replace(path=path).geturl()
        if path.startswith("/p/"):
            return normalized_url, self.INSTAGRAM_POST_DATASET
        if path.startswith("/reel/"):
            return normalized_url, self.INSTAGRAM_REEL_DATASET
        raise ValueError("Instagram URL must point to a post or reel")

    @staticmethod
    def _find_video_url(records: list[dict[str, object]]) -> str:
        for record in records:
            video_url = record.get("video_url")
            if isinstance(video_url, str) and video_url:
                return video_url

            for item in record.get("post_content", []):
                if isinstance(item, dict):
                    item_type = str(item.get("type", "")).lower()
                    item_url = item.get("url")
                    if item_type == "video" and isinstance(item_url, str) and item_url:
                        return item_url

            videos = record.get("videos", [])
            if isinstance(videos, list):
                for item in videos:
                    if isinstance(item, str) and item:
                        return item
                    if isinstance(item, dict):
                        item_url = item.get("url")
                        if isinstance(item_url, str) and item_url:
                            return item_url

        raise RuntimeError("BrightData did not return a video URL for this Instagram URL")
