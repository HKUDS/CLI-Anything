"""Tests for the BrightData API adapter."""

import json
from urllib.parse import parse_qs, urlparse

import pytest

from cli_anything.shotcut.core.media_download.adapters import BrightDataApiClient


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self._payload


class FakeOpener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        return next(self.responses)


def test_trigger_starts_dataset_job():
    opener = FakeOpener([FakeResponse({"snapshot_id": "snapshot-1"})])
    client = BrightDataApiClient("api-key", opener=opener)

    snapshot_id = client.trigger("dataset-1", "https://instagram.com/p/example/")

    assert snapshot_id == "snapshot-1"
    query = parse_qs(urlparse(opener.requests[0][0].full_url).query)
    assert query["dataset_id"] == ["dataset-1"]
    assert query["format"] == ["json"]


def test_wait_for_snapshot_polls_until_records_are_ready():
    opener = FakeOpener(
        [
            FakeResponse({"status": "running"}),
            FakeResponse([{"video_url": "https://cdn.test/video.mp4"}]),
        ]
    )
    sleeps = []
    client = BrightDataApiClient(
        "api-key",
        retry_count=2,
        poll_interval_seconds=3,
        opener=opener,
        sleeper=sleeps.append,
    )

    records = client.wait_for_snapshot("snapshot-1")

    assert records == [{"video_url": "https://cdn.test/video.mp4"}]
    assert sleeps == [3]


def test_wait_for_snapshot_raises_for_failed_job():
    opener = FakeOpener([FakeResponse({"status": "failed", "message": "blocked"})])
    client = BrightDataApiClient("api-key", opener=opener)

    with pytest.raises(RuntimeError, match="blocked"):
        client.wait_for_snapshot("snapshot-1")
