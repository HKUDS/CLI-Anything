"""BrightData dataset API adapter."""

import json
import time
from collections.abc import Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class BrightDataApiClient:
    TRIGGER_URL = "https://api.brightdata.com/datasets/v3/trigger"
    SNAPSHOT_URL = "https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"

    def __init__(
        self,
        api_key: str,
        timeout_seconds: float = 60.0,
        retry_count: int = 60,
        poll_interval_seconds: float = 2.0,
        opener: Callable[..., object] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("BRIGHT_DATA_API_KEY is required for Instagram downloads")
        if retry_count < 1:
            raise ValueError("BrightData retry_count must be at least 1")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._retry_count = retry_count
        self._poll_interval_seconds = poll_interval_seconds
        self._opener = opener or urlopen
        self._sleeper = sleeper or time.sleep

    def trigger(self, dataset_id: str, source_url: str) -> str:
        response = self._request(
            "POST",
            self.TRIGGER_URL,
            params={
                "dataset_id": dataset_id,
                "format": "json",
                "uncompressed_webhook": "true",
                "include_errors": "false",
            },
            payload=[{"url": source_url}],
        )
        snapshot_id = response.get("snapshot_id")
        if not isinstance(snapshot_id, str) or not snapshot_id:
            raise RuntimeError("BrightData did not return a snapshot ID")
        return snapshot_id

    def wait_for_snapshot(self, snapshot_id: str) -> list[dict[str, object]]:
        for attempt in range(self._retry_count):
            response = self._request(
                "GET",
                self.SNAPSHOT_URL.format(snapshot_id=snapshot_id),
                params={"format": "json"},
            )
            records = self._extract_records(response)
            if records is not None:
                return records

            status = response.get("status")
            if status == "failed":
                message = response.get("message") or "BrightData snapshot failed"
                raise RuntimeError(str(message))
            if status == "ready":
                raise RuntimeError("BrightData snapshot was ready but contained no data")
            if attempt < self._retry_count - 1:
                self._sleeper(self._poll_interval_seconds)

        raise TimeoutError(
            f"BrightData snapshot did not finish after {self._retry_count} attempts"
        )

    def _request(
        self,
        method: str,
        url: str,
        params: dict[str, str],
        payload: object | None = None,
    ) -> dict[str, object] | list[object]:
        request_url = f"{url}?{urlencode(params)}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            request_url,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                parsed = json.loads(response.read().decode("utf-8"))
        except Exception as error:
            raise RuntimeError(f"BrightData request failed: {error}") from error
        if not isinstance(parsed, (dict, list)):
            raise RuntimeError("BrightData returned an invalid JSON response")
        return parsed

    @staticmethod
    def _extract_records(
        response: dict[str, object] | list[object],
    ) -> list[dict[str, object]] | None:
        records: object = response
        if isinstance(response, dict) and isinstance(response.get("data"), list):
            records = response["data"]
        if not isinstance(records, list):
            return None
        if not records:
            raise RuntimeError("BrightData returned an empty snapshot")
        if not all(isinstance(record, dict) for record in records):
            raise RuntimeError("BrightData returned an invalid snapshot record")
        return records  # type: ignore[return-value]
