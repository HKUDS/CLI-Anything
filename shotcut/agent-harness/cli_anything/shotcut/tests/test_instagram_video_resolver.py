"""Tests for the BrightData Instagram resolver."""

import pytest

from cli_anything.shotcut.core.media_download.adapters.platforms import (
    BrightDataInstagramVideoResolver,
)


class FakeBrightDataApi:
    def __init__(self, records):
        self.records = records
        self.trigger_calls = []
        self.wait_calls = []

    def trigger(self, dataset_id: str, source_url: str) -> str:
        self.trigger_calls.append((dataset_id, source_url))
        return "snapshot-123"

    def wait_for_snapshot(self, snapshot_id: str):
        self.wait_calls.append(snapshot_id)
        return self.records


def test_resolves_post_video_from_post_content():
    api = FakeBrightDataApi(
        [{"post_content": [{"type": "video", "url": "https://cdn.test/post.mp4"}]}]
    )
    resolver = BrightDataInstagramVideoResolver(api)

    result = resolver.resolve("https://www.instagram.com/p/example/")

    assert result.media_url == "https://cdn.test/post.mp4"
    assert result.platform == "instagram"
    assert api.trigger_calls == [
        (resolver.INSTAGRAM_POST_DATASET, "https://www.instagram.com/p/example/")
    ]
    assert api.wait_calls == ["snapshot-123"]


def test_normalizes_reels_url_and_resolves_reel_video():
    api = FakeBrightDataApi([{"video_url": "https://cdn.test/reel.mp4"}])
    resolver = BrightDataInstagramVideoResolver(api)

    result = resolver.resolve("https://instagram.com/reels/example/?foo=bar")

    assert result.media_url == "https://cdn.test/reel.mp4"
    assert api.trigger_calls == [
        (resolver.INSTAGRAM_REEL_DATASET, "https://instagram.com/reel/example/?foo=bar")
    ]


def test_rejects_unsupported_instagram_url():
    resolver = BrightDataInstagramVideoResolver(FakeBrightDataApi([]))

    assert resolver.can_resolve("https://www.instagram.com/accounts/login/") is False
    with pytest.raises(ValueError, match="post or reel"):
        resolver.resolve("https://www.instagram.com/accounts/login/")


def test_raises_when_instagram_response_has_no_video():
    resolver = BrightDataInstagramVideoResolver(FakeBrightDataApi([{"photos": ["x"]}]))

    with pytest.raises(RuntimeError, match="did not return a video URL"):
        resolver.resolve("https://www.instagram.com/p/example/")
